// Copyright 2012 Foursquare Labs Inc. All Rights Reserved.
package io.fsq.twofishes.indexer.importers.geonames

import io.fsq.twofishes.core.YahooWoeTypes
import io.fsq.twofishes.gen._
import io.fsq.twofishes.indexer.mongo.{GeocodeStorageWriteService, IndexerQueryExecutor}
import io.fsq.twofishes.indexer.mongo.RogueImplicits._
import io.fsq.twofishes.indexer.util.{GeocodeRecord, SlugEntry, SlugEntryMap}
import io.fsq.twofishes.model.gen.ThriftGeocodeRecord
import io.fsq.twofishes.util.{Helpers, NameUtils, SlugBuilder, StoredFeatureId}
import java.io.File
import scala.collection.JavaConverters._
import scala.collection.mutable.{HashMap, HashSet}

// TODO
// stop using string representations of "a:b" featureids everywhere, PLEASE

class SlugIndexer {
  val idToSlugMap = new HashMap[String, String]
  val slugEntryMap = new SlugEntryMap.SlugEntryMap
  var missingSlugList = new HashSet[String]

  def getBestSlug(id: StoredFeatureId): Option[String] = {
    idToSlugMap.get(id.humanReadableString)
  }

  def addMissingId(id: StoredFeatureId) {
    missingSlugList.add(id.humanReadableString)
  }

  Helpers.duration("readSlugs") { readSlugs() }

  def readSlugs() {
    // step 1 -- load existing slugs into ... memory?
    val files = List(
      new File("src/jvm/io/fsq/twofishes/indexer/data/computed/slugs.txt"),
      new File("src/jvm/io/fsq/twofishes/indexer/data/private/slugs.txt")
    )
    files.foreach(
      file =>
        if (file.exists) {
          val fileSource = scala.io.Source.fromFile(file)
          val lines = fileSource.getLines.toList.filterNot(_.startsWith("#"))
          lines.map(l => {
            val parts = l.split("\t")
            val slug = parts(0)
            val id = parts(1)
            val score = parts(2).toInt
            val deprecated = parts(3).toBoolean
            slugEntryMap(slug) = SlugEntry(id, score, deprecated = deprecated, permanent = true)
            if (!deprecated) {
              idToSlugMap(id) = slug
            }
          })
        }
    )
    println("read %d slugs".format(slugEntryMap.size))
  }

  val parentMap = new HashMap[StoredFeatureId, Option[GeocodeFeature]]

  def findFeature(fid: StoredFeatureId): Option[GeocodeServingFeature] = {
    // TODO: not in love with this talking directly to mongo, please fix
    val ret = IndexerQueryExecutor.instance
      .fetchOne(Q(ThriftGeocodeRecord).where(_.id eqs fid.longId))
      .map(r => new GeocodeRecord(r).toGeocodeServingFeature)
    if (ret.isEmpty) {
      println("couldn't find %s".format(fid))
    }
    ret
  }

  def findParent(fid: StoredFeatureId): Option[GeocodeFeature] = {
    parentMap.getOrElseUpdate(fid, findFeature(fid).map(_.feature))
  }

  def calculateSlugScore(f: GeocodeServingFeature): Int = {
    f.scoringFeatures.boost + f.scoringFeatures.population
  }

  def matchSlugs(id: String, servingFeature: GeocodeServingFeature, possibleSlugs: List[String]): Option[String] = {
    // println("trying to generate a slug for %s".format(id))
    possibleSlugs.foreach(slug => {
      // println("possible slug: %s".format(slug))
      val existingSlug = slugEntryMap.get(slug)
      val score = calculateSlugScore(servingFeature)
      existingSlug match {
        case Some(existing) => {
          if (!existing.permanent && score > existing.score) {
            val evictedId = existingSlug.get.id
            // println("evicting %s and recursing".format(evictedId))
            slugEntryMap(slug) = SlugEntry(id, score, deprecated = false, permanent = false)
            buildSlug(evictedId)
            return Some(slug)
          }
        }
        case _ => {
          // println("picking %s".format(slug))
          slugEntryMap(slug) = SlugEntry(id, score, deprecated = false, permanent = false)
          idToSlugMap(id) = slug
          return Some(slug)
        }
      }
    })
    // println("failed to find any slug")
    return None
  }

  def buildSlug(id: String) {
    val oldSlug = idToSlugMap.get(id)
    val oldEntry = oldSlug.map(slug => slugEntryMap(slug))
    var newSlug: Option[String] = None

    for {
      fid <- StoredFeatureId.fromHumanReadableString(id)
      servingFeature <- findFeature(fid)
      if (servingFeature.scoringFeatures.population > 0 ||
        servingFeature.scoringFeatures.boost > 0 ||
        servingFeature.feature.geometryOrThrow.wkbGeometryOption.nonEmpty ||
        servingFeature.feature.woeTypeOption.exists(YahooWoeTypes.isAdminWoeType) ||
        (servingFeature.feature.attributesOption.exists(_.adm1capOption.exists(a => a)) ||
          servingFeature.feature.attributesOption.exists(_.adm0capOption.exists(a => a))))
    } {
      val parents = servingFeature.scoringFeatures.parentIds
        .flatMap(StoredFeatureId.fromLong _)
        .flatMap(findParent _)
        .toList
      var possibleSlugs = SlugBuilder.makePossibleSlugs(servingFeature.feature, parents)

      // if a city is bigger than 2 million people, we'll attempt to use the bare city name as the slug
      // unless it's the US, where I'd rather have consistency of always doing city-state
      if (servingFeature.scoringFeatures.population > 2000000 && servingFeature.feature.ccOrThrow != "US") {
        possibleSlugs = NameUtils
          .bestName(servingFeature.feature, Some("en"), false)
          .toList
          .map(n => SlugBuilder.normalize(n.name)) ++ possibleSlugs
      }

      newSlug = matchSlugs(id, servingFeature, possibleSlugs)
      if (newSlug.isEmpty && possibleSlugs.nonEmpty) {
        var extraDigit = 1
        var slugFound = false
        while (!newSlug.isEmpty) {
          newSlug = matchSlugs(id, servingFeature, possibleSlugs.map(s => "%s-%d".format(s, extraDigit)))
          extraDigit += 1
        }
      }
    }
    if (newSlug != oldSlug) {
      println("deprecating old slug for %s %s -> %s".format(id, oldSlug, newSlug.getOrElse("newslug")))
      oldEntry.map(_.deprecated = true)
    }
  }

  def buildMissingSlugs() {
    println("building missing slugs for %d fetures".format(missingSlugList.size))
    // step 2 -- compute slugs for records without
    for {
      (id, index) <- missingSlugList.zipWithIndex
    } {
      if (index % 10000 == 0) {
        println("built %d of %d slugs".format(index, missingSlugList.size))
      }
      buildSlug(id)
    }

    // step 3 -- write new slug file
    println("writing new slug map for %d features".format(slugEntryMap.size))
    val p = new java.io.PrintWriter(new File("src/jvm/io/fsq/twofishes/indexer/data/computed/slugs.txt"))
    slugEntryMap.keys.toList.sorted.foreach(slug => p.println("%s\t%s".format(slug, slugEntryMap(slug))))
    p.close()
  }

  def writeMissingSlugs(store: GeocodeStorageWriteService) {
    for {
      (id, index) <- missingSlugList.zipWithIndex
      slug <- idToSlugMap.get(id)
      fid <- StoredFeatureId.fromHumanReadableString(id)
    } {
      if (index % 10000 == 0) {
        println("flushed %d of %d slug to mongo".format(index, missingSlugList.size))
      }
      store.addSlugToRecord(fid, slug)
    }
  }
}

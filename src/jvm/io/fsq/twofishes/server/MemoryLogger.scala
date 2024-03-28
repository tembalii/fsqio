//  Copyright 2012 Foursquare Labs Inc. All Rights Reserved
package io.fsq.twofishes.server

import io.fsq.geo.quadtree.CountryRevGeo
import io.fsq.twitter.ostrich.stats.Stats
import io.fsq.twofishes.gen.{CommonGeocodeRequestParams, GeocodeRequest}
import io.fsq.twofishes.util.{DurationUtils, TwofishesLogger}
import java.util.Date
import scala.collection.JavaConverters._
import scala.collection.mutable.ListBuffer

object MemoryLogger {
  def apply(req: GeocodeRequest, revGeo: CountryRevGeo): MemoryLogger = {
    new MemoryLogger(GeocodeRequestUtils.geocodeRequestToCommonRequestParams(req, revGeo))
  }
}

class MemoryLogger(req: CommonGeocodeRequestParams) extends TwofishesLogger {
  val startTime = new Date()

  def timeSinceStart = {
    new Date().getTime() - startTime.getTime()
  }

  val lines: ListBuffer[String] = new ListBuffer()

  def ifDebug(formatSpecifier: String, va: Any*) {
    if (va.isEmpty) {
      ifLevelDebug(1, "%s", formatSpecifier)
    } else {
      ifLevelDebug(1, formatSpecifier, va: _*)
    }
  }

  def ifLevelDebug(level: Int, formatSpecifier: String, va: Any*) {
    if (level >= 0 && req.debug >= level) {
      val finalString = if (va.isEmpty) {
        formatSpecifier
      } else {
        formatSpecifier.format(va: _*)
      }
      lines.append("%d: %s".format(timeSinceStart, finalString))
    }
  }

  def getLines: List[String] = lines.toList

  def toOutput(): String = lines.mkString("<br>\n");

  def logDuration[T](ostrichKey: String, what: String)(f: => T): T = {
    val (rv, duration) = DurationUtils.inNanoseconds(f)
    Stats.addMetric(ostrichKey + "_usec", duration.inMicroseconds.toInt)
    ifDebug("%s in %s µs / %s ms", what, duration.inMicroseconds, duration.inMilliseconds)
    rv
  }
}

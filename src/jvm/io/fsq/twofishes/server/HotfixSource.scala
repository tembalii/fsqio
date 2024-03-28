// Copyright 2014 Foursquare Labs Inc. All Rights Reserved.
package io.fsq.twofishes.server

import io.fsq.twofishes.gen.GeocodeServingFeatureEdit

trait HotfixSource {
  def getEdits(): Seq[GeocodeServingFeatureEdit]
  def refresh(): Unit
}

class EmptyHotfixSource extends HotfixSource {
  def getEdits(): Seq[GeocodeServingFeatureEdit] = Nil
  def refresh(): Unit = {}
}

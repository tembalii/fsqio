/*
 * Copyright 2009 Twitter, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package io.fsq.twitter.ostrich.stats

import com.fasterxml.jackson.core.JsonGenerator
import com.fasterxml.jackson.databind.{JsonSerializer, SerializerProvider}
import com.fasterxml.jackson.databind.annotation.JsonSerialize
import scala.collection.Map

/**
  * A set of data points summarized into a histogram, mean, min, and max.
  * Distributions are immutable.
  */
@JsonSerialize(using = classOf[DistributionJsonSerializer])
case class Distribution(histogram: Histogram) {
  def this() = this(Histogram())

  def count = histogram.count
  def sum = histogram.sum
  def minimum = histogram.minimum
  def maximum = histogram.maximum
  def average = {
    val count = histogram.count
    if (count > 0) histogram.sum / count else 0.0
  }

  override def equals(other: Any) = other match {
    case t: Distribution => t.histogram == histogram
    case _ => false
  }

  def -(other: Distribution): Distribution = Distribution(histogram - other.histogram)

  override def toString = {
    val out = toMap
    out.keys.toSeq.sorted
      .map { key =>
        "%s=%d".format(key, out(key))
      }
      .mkString("(", ", ", ")")
  }

  def toMapWithoutPercentiles = {
    Map[String, Long]("count" -> histogram.count) ++ (
      // If there are no events then derived values are meaningless; so elide them.
      if (histogram.count > 0) {
        Map[String, Long](
          "sum" -> histogram.sum,
          "maximum" -> histogram.maximum,
          "minimum" -> histogram.minimum,
          "average" -> average.toLong
        )
      } else {
        Map.empty[String, Long]
      }
    )
  }

  private def percentile(percentile: Double) = {
    histogram.getPercentile(percentile)
  }

  def toMap: Map[String, Long] = {
    toMapWithoutPercentiles ++
      // If there are no events then derived values are meaningless; so elide them.
      (if (histogram.count > 0) {
         Map[String, Long](
           "p50" -> percentile(0.5),
           "p90" -> percentile(0.90),
           "p95" -> percentile(0.95),
           "p99" -> percentile(0.99),
           "p999" -> percentile(0.999),
           "p9999" -> percentile(0.9999)
         )
       } else {
         Map.empty[String, Long]
       })
  }
}

class DistributionJsonSerializer extends JsonSerializer[Distribution] {
  override def serialize(
    distribution: Distribution,
    jsonGenerator: JsonGenerator,
    serializerProvider: SerializerProvider
  ): Unit = {
    jsonGenerator.writeStartObject()
    // sorting might not be necessary
    // https://github.com/twitter/ostrich/issues/78
    distribution.toMap.toList.sorted.foreach(Function.tupled(jsonGenerator.writeObjectField))
    jsonGenerator.writeEndObject()
  }
}

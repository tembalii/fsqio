// Copyright 2015 Foursquare Labs Inc. All Rights Reserved.

package io.fsq.spindle.common.thrift.bson

import java.io.{EOFException, InputStream}

/**
  * some helper functions for reading and writing little endian numbers from streams
  */
object StreamHelper {
  val MaxDocSize = 16 * 1024 * 1024

  def readInt(is: InputStream): Int = {
    val ch1 = 0xFF & is.read()
    val ch2 = 0xFF & is.read()
    val ch3 = 0xFF & is.read()
    val ch4 = 0xFF & is.read()

    // little endian
    ((ch4 << 24) + (ch3 << 16) + (ch2 << 8) + (ch1 << 0))
  }

  def writeInt(bytes: Array[Byte], offset: Int, i: Int) {
    bytes(offset) = ((i << 24) >>> 24).toByte
    bytes(offset + 1) = ((i << 16) >>> 24).toByte
    bytes(offset + 2) = ((i << 8) >>> 24).toByte
    bytes(offset + 3) = (i >>> 24).toByte
  }

  def readLong(is: InputStream): Long = {
    val ch1 = 0XFFL & is.read()
    val ch2 = 0XFFL & is.read()
    val ch3 = 0XFFL & is.read()
    val ch4 = 0XFFL & is.read()
    val ch5 = 0XFFL & is.read()
    val ch6 = 0XFFL & is.read()
    val ch7 = 0XFFL & is.read()
    val ch8 = 0XFFL & is.read()

    // little endian
    (
      (ch8 << 56) + (ch7 << 48) + (ch6 << 40) + (ch5 << 32) +
        (ch4 << 24) + (ch3 << 16) + (ch2 << 8) + (ch1 << 0)
    )
  }

  def readFully(is: InputStream, bytes: Array[Byte], startOffset: Int, length: Int): Unit = {
    if (bytes.length < length + startOffset) {
      throw new IllegalArgumentException("Buffer is too small")
    }

    var offset = startOffset;
    var toRead = length
    while (toRead > 0) {
      val bytesRead = is.read(bytes, offset, toRead)
      if (bytesRead < 0) {
        throw new EOFException()
      }
      toRead -= bytesRead
      offset += bytesRead
    }
  }
}

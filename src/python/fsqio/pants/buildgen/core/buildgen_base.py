# coding=utf-8
# Copyright 2016 Foursquare Labs Inc. All Rights Reserved.

from __future__ import absolute_import, division, print_function, unicode_literals

from pants.task.task import Task
from pants.util.memo import memoized_property

from fsqio.pants.buildgen.core.subsystems.buildgen_subsystem import BuildgenSubsystem


class BuildgenBase(Task):
  """"A base task that provides the buildgen subsystem to its implementers."""

  @classmethod
  def subsystem_dependencies(cls):
    return super(BuildgenBase, cls).subsystem_dependencies() + (BuildgenSubsystem.Factory,)

  @classmethod
  def implementation_version(cls):
    return super(BuildgenBase, cls).implementation_version() + [('BuildgenBase', 2)]

  @memoized_property
  def buildgen_subsystem(self):
    # TODO(pl): When pants is a proper library dep, remove this ignore.
    # pylint: disable=no-member
    return BuildgenSubsystem.Factory.global_instance().create()

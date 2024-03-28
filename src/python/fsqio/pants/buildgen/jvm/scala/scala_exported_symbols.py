# coding=utf-8
# Copyright 2014 Foursquare Labs Inc. All Rights Reserved.

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from pants.backend.jvm.targets.junit_tests import JUnitTests
from pants.backend.jvm.targets.scala_library import ScalaLibrary
from pants.backend.jvm.tasks.nailgun_task import NailgunTask

from fsqio.pants.buildgen.core.source_analysis_task import SourceAnalysisTask
from fsqio.pants.buildgen.jvm.scala.scalac_buildgen_task_mixin import ScalacBuildgenTaskMixin


class MapScalaExportedSymbols(NailgunTask, SourceAnalysisTask, ScalacBuildgenTaskMixin):
  """Provides a product mapping source files to the symbols importable from that source."""
  @classmethod
  def analysis_product_name(cls):
    return 'scala_source_to_exported_symbols'

  @classmethod
  def implementation_version(cls):
    return super(MapScalaExportedSymbols, cls).implementation_version() + [('MapScalaExportedSymbols', 2)]

  @property
  def claimed_target_types(self):
    return (ScalaLibrary, JUnitTests)

  def targets(self):
    return self.context.build_graph.targets(lambda t: isinstance(t, self.claimed_target_types))

  @classmethod
  def register_options(cls, register):
    super(MapScalaExportedSymbols, cls).register_options(register)
    cls.register_scalac_buildgen_jvm_tools(register)

  def is_analyzable(self, source):
    return os.path.splitext(source)[1] == '.scala'

  @classmethod
  def prepare(cls, options, round_manager):
    super(MapScalaExportedSymbols, cls).prepare(options, round_manager)
    round_manager.require_data('scala')

  def analyze_sources(self, sources):
    return self.map_exported_symbols(sources, self.runjava)

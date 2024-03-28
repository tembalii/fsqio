# coding=utf-8
# Copyright 2014 Foursquare Labs Inc. All Rights Reserved.

from __future__ import absolute_import, division, print_function, unicode_literals

from contextlib import closing
from itertools import chain
import json
import os
import re
from zipfile import BadZipfile, ZipFile

from pants.backend.jvm.targets.jar_library import JarLibrary
from pants.base.exceptions import TaskError
from pants.invalidation.cache_manager import VersionedTargetSet
from pants.task.task import Task
from pants.util.dirutil import safe_mkdir


class MapThirdPartyJarSymbols(Task):

  @classmethod
  def product_types(cls):
    return [
      'third_party_jar_symbols',
    ]

  @classmethod
  def prepare(cls, options, round_manager):
    super(MapThirdPartyJarSymbols, cls).prepare(options, round_manager)
    round_manager.require_data('compile_classpath')
    round_manager.require_data('java')
    round_manager.require_data('scala')

  CLASSFILE_RE = re.compile(r'(?P<path_parts>(?:\w+/)+)'
                            r'(?P<file_part>.*?)'
                            r'\.class')
  CLASS_NAME_RE = re.compile(r'[a-zA-Z]\w*')

  @classmethod
  def implementation_version(cls):
    return super(MapThirdPartyJarSymbols, cls).implementation_version() + [('MapThirdPartyJarSymbols', 2)]

  def fully_qualified_classes_from_jar(self, jar_abspath):
    jar_contents = self._dump_jar_contents(jar_abspath)
    classlist = set()
    for qualified_file_name in self._dump_jar_contents(jar_abspath):
      match = self.CLASSFILE_RE.match(qualified_file_name)
      if match is not None:
        file_part = match.groupdict()['file_part']
        path_parts = match.groupdict()['path_parts']
        path_parts = filter(None, path_parts.split('/'))
        package = '.'.join(path_parts)
        non_anon_file_part = file_part.split('$$')[0]
        nested_classes = non_anon_file_part.split('$')
        for i in range(len(nested_classes)):
          if not self.CLASS_NAME_RE.match(nested_classes[i]):
            break
          nested_class_name = '.'.join(nested_classes[:i + 1])
          fully_qualified_class = '.'.join([package, nested_class_name])
          classlist.add(fully_qualified_class)
    return classlist

  def _dump_jar_contents(self, jar_abspath):
    # TODO(mateo): Should convert to context.util.open_zip which, it turns out, is pretty damn similar to this method.
    try:
      with closing(ZipFile(jar_abspath)) as dep_zip:
        return dep_zip.namelist()  # pylint: disable=no-member
    except BadZipfile as e:
      raise TaskError(
        "Could not unzip jar file: {}\nYou may have a corrupted file. Delete it and try again: {}"
        .format(e, os.path.realpath(jar_abspath))
      )

  def execute(self):
    products = self.context.products
    targets = self.context.targets(lambda t: isinstance(t, JarLibrary))

    with self.invalidated(targets, invalidate_dependents=False) as invalidation_check:
      global_vts = VersionedTargetSet.from_versioned_targets(invalidation_check.all_vts)
      vts_workdir = os.path.join(self._workdir, global_vts.cache_key.hash)
      vts_analysis_file = os.path.join(vts_workdir, 'buildgen_analysis.json')
      if invalidation_check.invalid_vts or not os.path.exists(vts_analysis_file):
        classpath = self.context.products.get_data('compile_classpath')
        jar_entries = classpath.get_for_targets(targets)
        all_jars = [jar for _, jar in jar_entries]
        calculated_analysis = {}
        calculated_analysis['hash'] = global_vts.cache_key.hash
        calculated_analysis['jar_to_symbols_exported'] = {}
        for jar_path in sorted(all_jars):
          if os.path.splitext(jar_path)[1] != '.jar':
            continue
          fully_qualified_classes = list(self.fully_qualified_classes_from_jar(jar_path))
          calculated_analysis['jar_to_symbols_exported'][jar_path] = {
            'fully_qualified_classes': fully_qualified_classes,
          }
        calculated_analysis_json = json.dumps(calculated_analysis)
        safe_mkdir(vts_workdir)
        with open(vts_analysis_file, 'wb') as f:
          f.write(calculated_analysis_json)
        if self.artifact_cache_writes_enabled():
          self.update_artifact_cache([(global_vts, [vts_analysis_file])])
      with open(vts_analysis_file, 'rb') as f:
        analysis = json.loads(f.read())

      third_party_jar_symbols = set(chain.from_iterable(
        v['fully_qualified_classes'] for v in analysis['jar_to_symbols_exported'].values()
      ))
      products.safe_create_data('third_party_jar_symbols', lambda: third_party_jar_symbols)

  def check_artifact_cache_for(self, invalidation_check):
    global_vts = VersionedTargetSet.from_versioned_targets(invalidation_check.all_vts)
    return [global_vts]

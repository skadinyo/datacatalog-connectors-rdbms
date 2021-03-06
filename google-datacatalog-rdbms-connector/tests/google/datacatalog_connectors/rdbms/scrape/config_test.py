#!/usr/bin/python
#
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import unittest
import mock

from google.datacatalog_connectors.commons_test import utils
from google.datacatalog_connectors.rdbms.scrape import config, config_constants


class ConfigTestCase(unittest.TestCase):
    __MODULE_PATH = os.path.dirname(os.path.abspath(__file__))

    @mock.patch('yaml.load')
    def test_config_should_deliver_options_chosen_by_user(self, yaml_load):
        yaml_load.return_value = {
            config_constants.REFRESH_OPTION: True,
            config_constants.ROW_COUNT_OPTION: True
        }
        test_config_path = utils.Utils.get_resolved_file_name(
            self.__MODULE_PATH, 'ingest_cfg.yaml')
        user_config = config.Config(test_config_path)

        self.assertEqual([config_constants.ROW_COUNT_OPTION],
                         user_config.get_chosen_metadata_options())

    @mock.patch('yaml.load')
    def test_config_should_not_deliver_options_not_chosen_by_user(
            self, yaml_load):
        yaml_load.return_value = {
            config_constants.REFRESH_OPTION: True,
            config_constants.ROW_COUNT_OPTION: False
        }
        test_config_path = utils.Utils.get_resolved_file_name(
            self.__MODULE_PATH, 'ingest_cfg.yaml')
        user_config = config.Config(test_config_path)

        self.assertEqual([], user_config.get_chosen_metadata_options())

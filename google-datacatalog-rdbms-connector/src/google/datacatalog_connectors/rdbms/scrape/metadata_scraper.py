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

import logging
import warnings
import time

from .metadata_normalizer import MetadataNormalizer

import pandas as pd


class MetadataScraper:

    def __init__(self):
        pass

    def get_metadata(self,
                     metadata_definition,
                     connection_args=None,
                     external_connection_args=None,
                     query=None,
                     csv_path=None,
                     user_config=None):
        dataframe = self._get_metadata_as_dataframe(metadata_definition,
                                                    connection_args, external_connection_args, query,
                                                    csv_path, user_config)

        return MetadataNormalizer.to_metadata_dict(dataframe,
                                                   metadata_definition)

    def _get_metadata_as_dataframe(self,
                                   metadata_definition,
                                   connection_args=None,
                                   external_connection_args=None,
                                   query=None,
                                   csv_path=None,
                                   user_config=None):
        
        if csv_path:
            logging.info('Scrapping metadata from csv path: "%s"', csv_path)
            dataframe = self._get_metadata_from_csv(csv_path)
        elif connection_args and len(connection_args.keys()) > 0:
            logging.info('Scrapping basic metadata from connection_args')
            dataframe = self._get_base_metadata_from_rdbms_connection(
                connection_args, query)
        else:
            raise Exception('Must supply either connection_args or csv_path')

        logging.info('Scrapping additional metadata from connection_args,'
                     'if configured')
        dataframe = self._enrich_metadata_based_on_user_config(
            user_config, dataframe, connection_args, external_connection_args, metadata_definition)

        return dataframe

    def _get_base_metadata_from_rdbms_connection(self, connection_args, query):
        con = None
        try:
            con = self._create_rdbms_connection(connection_args)
            cur = con.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            dataframe = self._create_dataframe(rows)
            
            if len(rows) == 0:
                raise Exception('RDBMS is empty, no metadata to extract.')
            logging.info('=========== {} Row Count Metadata=========='.format(len(rows)))
            
            dataframe.columns = [item[0].lower() for item in cur.description]
            return dataframe
        except:  # noqa:E722
            logging.error(
                'Error connecting to the database to extract metadata.')
            raise
        finally:
            if con:
                con.close()

    def _create_dataframe(self, rows):
        return pd.DataFrame(rows)

    def _enrich_metadata_based_on_user_config(self, user_config, base_dataframe, connection_args, external_connection_args, metadata_definition):
        enriched_dataframe = base_dataframe

        # if user_config.refresh_metadata_tables:
        #     query_assembler = self._get_query_assembler()
        #     exact_table_names = MetadataNormalizer.\
        #         get_exact_table_names_from_dataframe(
        #             base_dataframe, metadata_definition)
        #     refresh_queries = query_assembler.get_refresh_metadata_queries(
        #         exact_table_names)
        #     logging.info('Refreshing metadata')
        #     self._refresh_metadata_from_rdbms_connection(
        #         connection_args, refresh_queries)

        if True:
            query_assembler = self._get_query_assembler()
            optional_queries = query_assembler.get_optional_queries()
            logging.info(
                'Scraping metadata according to configuration file: {}'.format(
                    optional_queries))
            print('Get Extra Metadata')
            additional_dataframe = \
                self._get_optional_metadata_from_rdbms_connection(
                    connection_args, optional_queries, base_dataframe,
                    metadata_definition)
            print('Get External Metadata')
            external_dataframe = self._get_external_metadata(external_connection_args, connection_args)
            
            enriched_dataframe = self._get_merged_dataframe_left(additional_dataframe, external_dataframe, metadata_definition)
            enriched_dataframe['index_list'] = enriched_dataframe['index_list'].fillna('')
            enriched_dataframe['replication'] = enriched_dataframe['replication'].fillna(False)
            print(enriched_dataframe)
        # enrich_metadata_dict = user_config.get_enrich_metadata_dict()
        # print('DEBUG')
        # print(enrich_metadata_dict)
        # if enrich_metadata_dict:
            # metadata_enricher = self._get_metadata_enricher()(
            #     metadata_definition, None)
            # enriched_dataframe = metadata_enricher.enrich(base_dataframe)

        return enriched_dataframe

    def _refresh_metadata_from_rdbms_connection(self, connection_args,
                                                refresh_queries):
        con = None
        try:
            con = self._create_rdbms_connection(connection_args)
            cur = con.cursor()
            start_update = time.time()
            for query in refresh_queries:
                self._execute_refresh_query(cur, query)
            end_update = time.time()
            logging.info(
                'Metadata analysis took {} seconds to run.'
                'You can turn it off in ingest_cfg.yaml configuration file, '
                'using refresh_metadata_tables flag'.format(end_update -
                                                            start_update))
        except:  # noqa:E722
            logging.error(
                'Error connecting to the database to update metadata.')
            raise
        finally:
            if con:
                con.close()

    def _get_optional_metadata_from_rdbms_connection(self, connection_args,
                                                     optional_queries,
                                                     base_dataframe,
                                                     metadata_definition):
        con = None
        merged_dataframe = base_dataframe
        try:
            con = self._create_rdbms_connection(connection_args)
            cur = con.cursor()
            for option, query in optional_queries.items():
                logging.info(
                    "Executing query to process configuration option {}".
                    format(option))
                cur.execute(query)
                rows = cur.fetchall()
                if len(rows) == 0:
                    warnings.warn(
                        "Query {} delivered no rows. Skipping it.".format(
                            query))
                else:
                    new_dataframe = self._create_dataframe(rows)
                    new_dataframe.columns = [
                        item[0].lower() for item in cur.description
                    ]
                    merged_dataframe = self._get_merged_dataframe(
                        base_dataframe, new_dataframe, metadata_definition)
            return merged_dataframe
        except:  # noqa:E722
            logging.error('Error connecting to the database '
                          'to extract optional metadata.')
            raise
        finally:
            if con:
                con.close()

    def _get_external_metadata(self, external_connection_args, connection_args):
        # import at the method level, because this flow is kinda conditional
        con = None
        from psycopg2 import connect
        try:
            con = connect(database=external_connection_args['database'],
                          host=external_connection_args['host'],
                          port=5432,
                          user=external_connection_args['user'],
                          password=external_connection_args['password'])
            cur = con.cursor()
            # TODO add it from file
            # TODO add db for the merger
            query = 'SELECT stb.source_table_name as table_name, stb.enabled as replication FROM public.slave_to_bq stb LEFT JOIN public.database_connection dc ON stb.db_id = dc.db_id WHERE dc.db_name = %(dbname)s;'
            cur.execute(query, {'dbname': connection_args['database']})
            rows = cur.fetchall()
            dt_frame = self._create_dataframe(rows)
            if len(rows) == 0:
                warnings.warn(
                        "Query {} delivered no rows. Skipping {} it.".format(
                            query, connection_args['database']))
                dt_frame['schema_name'] = 'public'
                dt_frame['table_name'] = ''
                dt_frame['replication'] = False
                return dt_frame 
            else:
                print(dt_frame)
                dt_frame.columns = [
                    item[0].lower() for item in cur.description
                ]
                # Hack
                dt_frame['schema_name'] = 'public'
                return dt_frame
        except:
            logging.error('Error in getting external metadata')
            raise
        finally:
            if con:
                con.close()

    def _get_merged_dataframe(self, old_df, new_df, metadata_definition):
        table_name_col = metadata_definition['table_def']['name']
        table_container_mame_col = metadata_definition['table_container_def'][
            'name']
        dataframe = pd.merge(old_df,
                             new_df,
                             on=[table_container_mame_col, table_name_col])
        return dataframe

    def _get_merged_dataframe_left(self, old_df, new_df, metadata_definition):
        table_name_col = metadata_definition['table_def']['name']
        table_container_mame_col = metadata_definition['table_container_def'][
            'name']
        dataframe = pd.merge(old_df,
                             new_df,
                             how='left',
                             on=[table_container_mame_col, table_name_col])
        return dataframe

    # To connect to the RDBMS, it's required to override this method.
    # If you are ingesting from a CSV file, this method is not used.
    def _create_rdbms_connection(self, connection_args):
        raise NotImplementedError(
            'Implementing this method is required to connect to a RDBMS!')

    @classmethod
    def _get_metadata_from_csv(cls, csv_path):
        return pd.read_csv(csv_path)

    def _get_query_assembler(self):
        raise NotImplementedError('Implementing this method is required '
                                  'to run multiple optional queries')

    def _get_metadata_enricher(self):
        raise NotImplementedError('Implementing this method is required '
                                  'to enrich metadata attributes')

    def _execute_refresh_query(self, cursor, query):
        """
        On update, some DBs deliver a table that has to be fetched
        after executing the query; others don't.
        What to do with results of update is RDBMS-specific,
        and these details have to be implemented in this method.
        """
        raise NotImplementedError(
            'Implementing this method is required to execute an update query '
            'in a DB-specific way')

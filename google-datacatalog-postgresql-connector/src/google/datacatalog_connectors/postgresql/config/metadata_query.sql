SELECT t.schemaname AS SCHEMA_NAME,
       t.tablename AS table_name,
       CASE
	   WHEN ns.oid = pg_my_temp_schema() THEN 'LOCAL TEMPORARY'::text
	   WHEN pc.relkind = 'r'::"char" THEN 'BASE TABLE'::text
	   WHEN pc.relkind = 'v'::"char" THEN 'VIEW'::text
	   WHEN pc.relkind = 'f'::"char" THEN 'FOREIGN TABLE'::text
	   ELSE NULL::text
		END AS table_type,
       c.attname AS column_name,
       c.attnotnull AS column_nullable,
       pg_catalog.format_type(c.atttypid, c.atttypmod) as column_type,
       CAST (pg_total_relation_size(pc.oid) AS FLOAT) / 1024 / 1024 AS table_size_mb
FROM pg_tables t
JOIN pg_namespace ns ON t.schemaname = ns.nspname
JOIN pg_class pc ON pc.relname = t.tablename AND pc.relnamespace = ns.oid
JOIN pg_attribute c ON c.attrelid = pc.oid
LEFT JOIN pg_attrdef ad ON ad.adrelid = c.attrelid AND c.attnum=ad.adnum
WHERE t.schemaname NOT IN ('pg_catalog',
                             'information_schema',
                             'pg_toast',
                             'gp_toolkit',
                             'pg_internal',
                             'pglogical',
                             'londiste',
                             'pgq',
                             'pgq_ext',
                             'pgq_node')
AND NOT c.attisdropped
ORDER BY t.tablename,
         c.attname;

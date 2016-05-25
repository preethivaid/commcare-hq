# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration, HqRunSQL

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0021_get_all_ledger_values_modified_since'),
    ]

    operations = [
        HqRunSQL(
            "DROP FUNCTION IF EXISTS get_all_reverse_indices(TEST[])",
            "SELECT 1"
        ),
        migrator.get_migration('get_all_reverse_indices.sql'),
    ]

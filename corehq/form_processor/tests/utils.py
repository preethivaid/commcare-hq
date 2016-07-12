import functools
from datetime import datetime
from uuid import uuid4

from couchdbkit import ResourceNotFound
from django.conf import settings
from nose.tools import nottest

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLog
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, FormAccessorSQL, LedgerAccessorSQL, LedgerReindexAccessor
)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, CaseTransaction, Attachment
from corehq.form_processor.parsers.form import process_xform_xml
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.config import PartitionConfig
from corehq.util.test_utils import unit_testing_only, run_with_multiple_configs, RunConfig
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import safe_delete


class FormProcessorTestUtils(object):

    @classmethod
    @unit_testing_only
    def delete_all_cases_forms_ledgers(cls, domain=None):
        cls.delete_all_ledgers(domain)
        cls.delete_all_cases(domain)
        cls.delete_all_xforms(domain)

    @classmethod
    @unit_testing_only
    def delete_all_cases(cls, domain=None):
        assert CommCareCase.get_db().dbname.startswith('test_')
        view_kwargs = {}
        if domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}],
            }

        cls._delete_all(
            CommCareCase.get_db(),
            'cases_by_server_date/by_server_modified_on',
            **view_kwargs
        )

        FormProcessorTestUtils.delete_all_sql_cases(domain)

    @staticmethod
    @unit_testing_only
    def delete_all_sql_cases(domain=None):
        CaseAccessorSQL.delete_all_cases(domain)

    @staticmethod
    def delete_all_ledgers(domain=None):
        if should_use_sql_backend(domain):
            FormProcessorTestUtils.delete_all_v2_ledgers(domain)
        else:
            FormProcessorTestUtils.delete_all_v1_ledgers(domain)

    @staticmethod
    @unit_testing_only
    def delete_all_v1_ledgers(domain=None):
        from casexml.apps.stock.models import StockReport
        from casexml.apps.stock.models import StockTransaction
        stock_report_ids = StockReport.objects.filter(domain=domain).values_list('id', flat=True)
        StockReport.objects.filter(domain=domain).delete()
        StockTransaction.objects.filter(report_id__in=stock_report_ids).delete()

    @staticmethod
    @unit_testing_only
    def delete_all_v2_ledgers(domain=None):
        def _delete_ledgers_for_case(case_id):
            transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id)
            form_ids = {tx.form_id for tx in transactions}
            for form_id in form_ids:
                LedgerAccessorSQL.delete_ledger_transactions_for_form([case_id], form_id)
            LedgerAccessorSQL.delete_ledger_values(case_id)

        if not domain:
            for db in _get_db_list_to_query():
                for ledger in LedgerReindexAccessor().get_docs(db, None, limit=10000):
                    _delete_ledgers_for_case(ledger.case_id)
        else:
            for case_id in CaseAccessorSQL.get_case_ids_in_domain(domain):
                _delete_ledgers_for_case(case_id)

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls, domain=None, user_id=None):
        view = 'couchforms/all_submissions_by_domain'
        view_kwargs = {}
        if domain and user_id:
            view = 'all_forms/view'
            view_kwargs = {
                'startkey': ['submission user', domain, user_id],
                'endkey': ['submission user', domain, user_id, {}],

            }
        elif domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}]
            }

        cls._delete_all(
            XFormInstance.get_db(),
            view,
            **view_kwargs
        )

        FormProcessorTestUtils.delete_all_sql_forms(domain, user_id)

    @staticmethod
    @unit_testing_only
    def delete_all_sql_forms(domain=None, user_id=None):
        FormAccessorSQL.delete_all_forms(domain, user_id)

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        cls._delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    @unit_testing_only
    def _delete_all(db, viewname, **view_kwargs):
        deleted = set()
        for row in db.view(viewname, reduce=False, **view_kwargs):
            doc_id = row['id']
            if id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass


run_with_all_backends = functools.partial(
    run_with_multiple_configs,
    run_configs=[
        # run with default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            post_run=lambda *args, **kwargs: args[0].tearDown()
        ),
        # run with inverse of default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            pre_run=lambda *args, **kwargs: args[0].setUp(),
        ),
    ]
)


def _get_db_list_to_query():
    if settings.USE_PARTITIONED_DATABASE:
        return PartitionConfig().get_form_processing_dbs()
    return [None]


@unit_testing_only
def post_xform(instance_xml, attachments=None, domain='test-domain'):
    """
    create a new xform and releases the lock

    this is a testing entry point only and is not to be used in real code

    """
    result = process_xform_xml(domain, instance_xml, attachments=attachments)
    with result.get_locked_forms() as xforms:
        FormProcessorInterface(domain).save_processed_models(xforms)
        return xforms[0]


@nottest
def create_form_for_test(domain, case_id=None, attachments=None, save=True):
    """
    Create the models directly so that these tests aren't dependent on any
    other apps. Not testing form processing here anyway.
    :param case_id: create case with ID if supplied
    :param attachments: additional attachments dict
    :param save: if False return the unsaved form
    :return: form object
    """
    from corehq.form_processor.utils import get_simple_form_xml

    form_id = uuid4().hex
    user_id = 'user1'
    utcnow = datetime.utcnow()

    form_xml = get_simple_form_xml(form_id, case_id)

    form = XFormInstanceSQL(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain
    )

    attachments = attachments or {}
    attachment_tuples = map(
        lambda a: Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachment_tuples.append(Attachment('form.xml', form_xml, 'text/xml'))

    FormProcessorSQL.store_attachments(form, attachment_tuples)

    cases = []
    if case_id:
        case = CommCareCaseSQL(
            case_id=case_id,
            domain=domain,
            type='',
            owner_id=user_id,
            opened_on=utcnow,
            modified_on=utcnow,
            modified_by=user_id,
            server_modified_on=utcnow,
        )
        case.track_create(CaseTransaction.form_transaction(case, form))
        cases = [case]

    if save:
        FormProcessorSQL.save_processed_models(ProcessedForms(form, None), cases)
    return form


@unit_testing_only
def set_case_property_directly(case, property_name, value):
    if should_use_sql_backend(case.domain):
        case.case_json[property_name] = value
    else:
        setattr(case, property_name, value)

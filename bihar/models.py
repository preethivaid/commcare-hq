import datetime
from casexml.apps.case.models import CommCareCase
from bihar.calculations import homevisit, pregnancy, postpartum
import fluff

A_DAY = datetime.timedelta(days=1)

class CareBiharFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ('care-bihar',)
    group_by = ['domain', 'owner_id']


    # home visit

    bp2 = homevisit.BPCalculator(days=75, n_visits=2)
    bp3 = homevisit.BPCalculator(days=45, n_visits=3)
    pnc = homevisit.VisitCalculator(schedule=(1, 3, 6), visit_type='pnc')
    ebf = homevisit.VisitCalculator(
        schedule=(14, 28, 60, 90, 120, 150),
        visit_type='eb',
    )
    cf = homevisit.VisitCalculator(
        schedule=[m * 30 for m in (6, 7, 8, 9, 12, 15, 18)],
        visit_type='cf',
    )

    upcoming_deliveries = homevisit.UpcomingDeliveryList()
    deliveries = homevisit.RecentDeliveryList()
    no_bp_counseling = homevisit.NoBPList()
    new_pregnancies = homevisit.RecentRegistrationList()
    no_ifa_tablets = homevisit.NoIFAList()
    no_emergency_prep = homevisit.NoEmergencyPrep()
    no_newborn_prep = homevisit.NoNewbornPrep()
    no_postpartum_counseling = homevisit.NoPostpartumCounseling()
    no_family_planning = homevisit.NoFamilyPlanning()

    # pregnancy

    hd = pregnancy.VisitedQuicklyBirthPlace(at='home')
    idv = pregnancy.VisitedQuicklyBirthPlace(at=('private', 'public'))
    idnb = pregnancy.BreastFedBirthPlace(at=('private', 'public'))
    born_at_home = pregnancy.LiveBirthPlace(at='home')
    born_at_public_hospital = pregnancy.LiveBirthPlace(at='public')
    born_in_transit = pregnancy.LiveBirthPlace(at='transit')
    born_in_private_hospital = pregnancy.LiveBirthPlace(at='private')

    # postpartum

    comp1 = postpartum.Complications(days=1)
    comp3 = postpartum.Complications(days=3)
    comp5 = postpartum.Complications(days=5)
    comp7 = postpartum.Complications(days=7)

    # newborn

    class Meta:
        app_label = 'bihar'

CareBiharFluffPillow = CareBiharFluff.pillow()
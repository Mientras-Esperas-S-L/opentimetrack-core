# The reporting app's only model: proof that the payslip summary was produced.
# Everything else here is computed on the fly from the clock record, which is
# the point --- a report that stored its own numbers could drift from the events
# it claims to summarise.
from apps.reports.payroll import PayrollPeriod, PayrollSummary

__all__ = ["PayrollPeriod", "PayrollSummary"]

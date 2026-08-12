"""Nobody decides their own case, unless there is nobody else.

A manager could file a correction on their own record and approve it. Two
clicks, both theirs, and the register said whatever they wanted it to say. The
same held for an administrator, and for leave.

That is not a permissions bug --- both roles are entitled to approve --- and it is
exactly why it survived every check. It is a segregation-of-duties gap: the
correction procedure exists so that a change to somebody's working time passes
through a second person, and for the two roles most able to abuse it, it did
not.

The one exception is real and has to be kept working. In a company with a
single administrator there is no second person, and refusing outright would
leave them unable to correct their own record at all --- for a self-employed
person or a two-person business, unable to use the product. So:

* if somebody else could decide, self-deciding is refused;
* if nobody else could, it goes ahead **and says so**, because a decision taken
  alone and one taken by a second person are not the same evidence, and whoever
  reads the register later is entitled to tell them apart.

The second half matters as much as the first. Silently allowing it would leave
the register unable to distinguish the two, which is the thing the procedure
was for.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError


def someone_else_could_decide(*, company, decider) -> bool:
    """Is there another active manager or administrator in the company?

    `User.objects` spans every company --- people are not a TenantOwnedModel,
    because sign-in has to find them before the company is known --- so the
    filter by tenant here is not belt and braces: without it, somebody else's
    manager would count as a second pair of eyes.
    """
    from apps.users.models import Role, User

    return (
        User.objects.filter(tenant=company, is_active=True, role__in=[Role.MANAGER, Role.ADMIN])
        .exclude(pk=decider.pk)
        .exists()
    )


def refuse_self_decision(*, subject, decider, company, what: str) -> bool:
    """Raises when `decider` is deciding their own case and need not be.

    Returns whether it went ahead alone, so the caller can record that fact
    rather than let it pass unmarked.
    """
    if subject.id != decider.id:
        return False

    if someone_else_could_decide(company=company, decider=decider):
        raise BusinessRuleError(
            code="cannot_decide_your_own",
            message=_(
                "You cannot resolve %(what)s of your own. Another manager or administrator "
                "has to, so that the change passes through a second person."
            )
            % {"what": what},
        )

    # Nobody else exists. Allowed, and the caller marks it.
    return True

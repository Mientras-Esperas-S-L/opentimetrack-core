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


def someone_else_could_decide(*, company, decider, subject=None) -> bool:
    """Is there somebody else who could decide **this** case?

    Not merely somebody else with the role. The question this answers is what
    stands between a person and deciding their own case, so an affirmative that
    names nobody able to act leaves the case with no way out at all.

    That is what happened. The only administrator asked to correct one of her
    own entries: refused, because a manager existed. The manager answered for
    one department, the administrator belonged to none, so the correction came
    back **404** to her --- 409 to the one person who could see it and 404 to
    the one who was supposed to decide. An entry of the working-time record left
    wrong with no way to fix it, which is art. 34.9, and a correction that could
    not be processed at all, which is art. 4.b.

    So the question is asked with the scope in hand:

    - **An administrator** reads the whole company, so any other active one
      counts.
    - **A manager** counts only if `subject` is inside a department they answer
      for --- or if the company turned scoping off, which puts every manager
      back in reach of everybody.

    `subject` is optional so older callers keep their meaning: without it the
    question falls back to the decider themselves, who is the subject in every
    self-decision this guards.

    `User.objects` spans every company --- people are not a TenantOwnedModel,
    because sign-in has to find them before the company is known --- so the
    filter by tenant here is not belt and braces: without it, somebody else's
    manager would count as a second pair of eyes.
    """
    from apps.common.scope import can_see
    from apps.users.models import Role, User

    subject = subject if subject is not None else decider

    others = User.objects.filter(tenant=company, is_active=True).exclude(pk=decider.pk)

    # Cualquier otra administradora sirve: leen la empresa entera.
    if others.filter(role=Role.ADMIN).exists():
        return True

    # Para las responsables la pregunta se le hace a `can_see`, y no se rehace
    # aquí. Ya sabe de la empresa que apagó el acotado, del departamento que se
    # dirige frente al que se pertenece, y de que mientras nadie lleve ninguno
    # toda responsable lee a todo el mundo. Escribir esa regla por segunda vez
    # fue el primer intento de arreglar esto, y se dejó fuera precisamente el
    # último caso.
    return any(can_see(otra, subject) for otra in others.filter(role=Role.MANAGER))


def refuse_self_decision(*, subject, decider, company, what: str) -> bool:
    """Raises when `decider` is deciding their own case and need not be.

    Returns whether it went ahead alone, so the caller can record that fact
    rather than let it pass unmarked.
    """
    if subject.id != decider.id:
        return False

    if someone_else_could_decide(company=company, decider=decider, subject=subject):
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

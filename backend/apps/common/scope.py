"""Whose working time somebody may read.

There used to be one answer to this, spelled out in seventeen places: *a worker
sees their own, a manager sees everybody*. The second half was wrong in a way
that is easy to miss because nothing on any screen shows it --- the person who
runs the gardening crew could read the sick leave of somebody in the office, and
leave is where illness shows.

Departments existed but were only a label to filter by. Now they name who
answers for whom, and that is what the scope is built from.

Four answers, and the third is the one that is new:

**An administrator** sees the whole company. That is what administering it is;
the four-eyes rule in `apps.common.four_eyes` is what stops them deciding about
themselves.

**A manager who was put in charge of departments** sees those, plus themselves.
Not the department they belong to --- somebody in the office can perfectly well
run the gardening crew, and conflating the two would give them the office's
records instead of the ones they answer for.

**A manager in charge of nothing, in a company where nobody is in charge of
anything** sees everybody, which is what the role meant before any of this. That
is deliberate and it is the hard call here. Narrowing them by default would mean
a company that signs up today, creates ten people and marks one as manager finds
a product that shows that manager nobody at all --- and the fix for a default
that looks broken on day one is that people turn it off, not that they discover
departments. The settings screen says out loud how many managers are still
unassigned.

**A manager in charge of nothing, in a company where somebody is** sees only
themselves. This is the correction to the paragraph above, and the reason is in
its own last sentence: assigning somebody a department is the act of narrowing
them. If assigning narrows, unassigning cannot widen --- yet it did, and by the
most ordinary route there is. Handing Obras over from one manager to another left
the first one reading the whole company, because *in charge of nothing* and
*nothing has been decided yet* were the same state. They are not: the first
manager put in charge of a department is what tells the two apart.

**A manager in a company that turned scoping off** sees everybody even when they
do run a department. Kept as a company setting: in a firm of twelve, departments
are an overhead nobody asked for.

**Everybody else** sees themselves.

`None` means *no restriction*, so the common case adds no query. Returning a
queryset of the whole company instead would be correct and would put a join on
every list in the product.
"""

from __future__ import annotations

from django.db.models import Q


def visible_people(user):
    """The people whose records `user` may read, or None for everybody.

    Callers filter with it rather than asking about one person at a time:

        scope = visible_people(request.user)
        if scope is not None:
            qs = qs.filter(employee__in=scope)
    """
    from apps.users.models import Department, User

    if not user.can_manage:
        return User.objects.filter(pk=user.pk)
    if user.is_admin or user.tenant.managers_see_whole_company:
        return None

    managed = Department.objects.filter(managers=user, tenant=user.tenant)
    if not managed.exists():
        # Nothing has been said about what they answer for --- but only while
        # nobody in the company answers for anything. Once somebody runs a
        # department, the mechanism is in use, and running none of them is an
        # answer rather than a silence. Without this, taking a department away
        # from a manager *widens* them to the whole company, which is the
        # opposite of what the administrator just asked for. See the module
        # docstring.
        if department_scoping_in_use(user.tenant):
            return User.objects.filter(pk=user.pk)
        return None

    # Filtered by tenant explicitly: `User.objects` is deliberately not
    # tenant-scoped, because at sign-in time there is no tenant yet.
    return User.objects.filter(
        Q(department__in=managed) | Q(pk=user.pk), tenant=user.tenant
    ).distinct()


def department_scoping_in_use(company) -> bool:
    """Whether this company has started using departments as a scope.

    The whole design turns on telling two states apart that look identical from
    a single manager's row: *nothing has been decided here yet* and *it has been
    decided, and you run none of them*. The first manager put in charge of a
    department is the moment one becomes the other.

    Before that moment a manager reads the whole company, because a product that
    shows a brand-new company's manager nobody at all gets its scoping switched
    off rather than its departments discovered. After it, a manager in charge of
    nothing reads only themselves --- otherwise handing a department over to a
    colleague would *widen* the first manager to the entire payroll, which is
    the opposite of what was asked for.
    """
    from apps.users.models import Department

    return Department.objects.filter(tenant=company, managers__isnull=False).exists()


def can_see(user, person) -> bool:
    """Whether `user` may read `person`'s record.

    For the object-level check, where there is one row rather than a queryset.
    """
    if person is None:
        return False
    if person.pk == user.pk:
        return True
    scope = visible_people(user)
    if scope is None:
        return user.can_manage
    return scope.filter(pk=person.pk).exists()


def unassigned_managers(company):
    """Managers in charge of no department.

    What that costs depends on `department_scoping_in_use`, and the settings
    screen says which of the two it is:

    - Nobody runs a department yet, so these managers read **everybody**. That
      is the one place the design trades privacy for not being broken on day
      one, and a trade nobody can see is not a trade, it is a hole.
    - Somebody does, so these managers read **only themselves** --- they cannot
      do the job they were given the role for, which is worth saying out loud
      too, and is what happens to whoever just handed their department over.
    """
    from apps.users.models import Department, Role, User

    if company.managers_see_whole_company:
        return User.objects.none()
    running = Department.objects.filter(tenant=company, managers__isnull=False).values("managers")
    return User.objects.filter(tenant=company, role=Role.MANAGER, is_active=True).exclude(
        pk__in=running
    )


def people_queryset(user):
    """Everybody `user` may read, always as a queryset.

    `visible_people` returns None for "no restriction" so the common case adds
    no join; this is for the callers that need something to iterate or to look
    a single person up in.
    """
    from apps.users.models import User

    scope = visible_people(user)
    return User.objects.filter(tenant=user.tenant) if scope is None else scope


def person_in_scope(user, pk):
    """The person with that id, if `user` may read them. None otherwise.

    Deliberately indistinguishable from "does not exist": telling somebody that
    a person exists but is out of their reach is telling them who works here,
    and the id is the one thing an outsider can guess at.
    """
    return people_queryset(user).filter(pk=pk).first()

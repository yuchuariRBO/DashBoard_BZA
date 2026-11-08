import uuid
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import OperationalError
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CommentForm, FilterForm, TicketForm, UpdateForm
from .models import Attachment, Notification, Status, Ticket
from .permissions import can_work, is_agent, manages_support, queue_for
from .services import Conflict, add_comment, create_ticket, update_ticket


def filtered(query, data):
    if data.get("q"):
        q = Q(subject__icontains=data["q"])
        try:
            q |= Q(pk=uuid.UUID(data["q"]))
        except ValueError:
            pass
        query = query.filter(q)
    for field in ("status", "priority", "category"):
        if data.get(field):
            query = query.filter(**{field: data[field]})
    if data.get("start"):
        query = query.filter(
            created_at__gte=timezone.make_aware(
                datetime.combine(data["start"], time.min)
            )
        )
    if data.get("end"):
        query = query.filter(
            created_at__lt=timezone.make_aware(
                datetime.combine(data["end"] + timedelta(days=1), time.min)
            )
        )
    if data.get("overdue"):
        query = query.exclude(status__in=[Status.RESOLVED, Status.CLOSED]).filter(
            resolution_due_at__lt=timezone.now()
        )
    return query


@login_required
def ticket_list(request):
    team = request.GET.get("team") == "1"
    if team and not is_agent(request.user):
        raise PermissionDenied
    qs = (
        queue_for(request.user)
        if team
        else Ticket.objects.filter(requester=request.user)
    )
    form = FilterForm(request.GET)
    qs = filtered(qs, form.cleaned_data) if form.is_valid() else qs.none()
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "support/list.html",
        {
            "tickets": Paginator(
                qs.select_related("category", "assignee"), 25
            ).get_page(request.GET.get("page")),
            "filters": form,
            "team": team,
            "querystring": params.urlencode(),
        },
    )


@login_required
def ticket_create(request):
    form = TicketForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ticket = create_ticket(request.user, form.cleaned_data)
        messages.success(
            request,
            "Solicitud creada. Podrá consultar las respuestas en la mesa de ayuda.",
        )
        return redirect("support:detail", pk=ticket.pk)
    from django.conf import settings

    return render(
        request,
        "support/create.html",
        {"form": form, "upload_limit_mb": settings.SUPPORT_MAX_UPLOAD_BYTES // 1048576},
    )


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        queue_for(request.user).select_related("requester", "category", "assignee"),
        pk=pk,
    )
    staff = can_work(request.user, ticket)
    comment_form = CommentForm(staff=staff, initial={"version": ticket.version})
    update_form = (
        UpdateForm(
            user=request.user,
            manager=manages_support(request.user),
            initial={
                "version": ticket.version,
                "status": ticket.status,
                "priority": ticket.priority,
                "assignee": ticket.assignee,
            },
        )
        if staff
        else None
    )
    code = 200
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "comment":
                comment_form = CommentForm(request.POST, request.FILES, staff=staff)
                if comment_form.is_valid():
                    add_comment(request.user, ticket, comment_form.cleaned_data)
                    return redirect("support:detail", pk=pk)
                code = 400
            elif action == "update" and staff:
                update_form = UpdateForm(
                    request.POST,
                    user=request.user,
                    manager=manages_support(request.user),
                )
                if update_form.is_valid():
                    update_ticket(request.user, ticket, update_form.cleaned_data)
                    return redirect("support:detail", pk=pk)
                code = 400
            elif action in ("confirm", "reopen"):
                try:
                    version = int(request.POST.get("version", ""))
                except ValueError:
                    raise ValidationError("Versión inválida.")
                update_ticket(
                    request.user,
                    ticket,
                    {
                        "version": version,
                        "status": Status.CLOSED if action == "confirm" else Status.OPEN,
                    },
                    requester_action=True,
                )
                return redirect("support:detail", pk=pk)
            else:
                raise PermissionDenied
        except (Conflict, OperationalError):
            messages.error(
                request,
                "El ticket cambió o está siendo actualizado. Recargue antes de continuar.",
            )
            code = 409
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            code = 400
    comments = ticket.comments.select_related("author")
    attachments = ticket.attachments.all()
    events = ticket.events.select_related("actor")
    if not staff:
        comments = comments.filter(internal=False)
        attachments = attachments.filter(
            Q(comment__isnull=True) | Q(comment__internal=False)
        )
        events = events.filter(staff_only=False)
    return render(
        request,
        "support/detail.html",
        {
            "ticket": ticket,
            "comments_list": comments,
            "attachments": attachments,
            "events": events,
            "staff": staff,
            "comment_form": comment_form,
            "update_form": update_form,
        },
        status=code,
    )


@login_required
def download(request, pk):
    item = get_object_or_404(
        Attachment.objects.select_related("ticket", "comment"),
        pk=pk,
        ticket__in=queue_for(request.user),
    )
    if (
        item.comment_id
        and item.comment.internal
        and not can_work(request.user, item.ticket)
    ):
        raise Http404
    try:
        stream = item.file.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(
        stream, as_attachment=True, filename=item.name, content_type=item.content_type
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def notifications(request):
    return render(
        request,
        "support/notifications.html",
        {
            "notifications": Paginator(
                Notification.objects.filter(recipient=request.user).select_related(
                    "ticket"
                ),
                25,
            ).get_page(request.GET.get("page"))
        },
    )


@login_required
@require_POST
def read_notification(request, pk):
    item = get_object_or_404(Notification, pk=pk, recipient=request.user)
    Notification.objects.filter(pk=item.pk, recipient=request.user).update(
        read_at=timezone.now()
    )
    return redirect("support:detail", pk=item.ticket_id)


@login_required
def dashboard(request):
    if not is_agent(request.user):
        raise PermissionDenied
    form = FilterForm(request.GET)
    qs = (
        filtered(queue_for(request.user), form.cleaned_data)
        if form.is_valid()
        else Ticket.objects.none()
    )
    stats = qs.aggregate(
        total=Count("pk"),
        open=Count(
            "pk", filter=Q(status__in=[Status.OPEN, Status.REVIEW, Status.PROGRESS])
        ),
        pending=Count("pk", filter=Q(status=Status.WAITING)),
        resolved=Count("pk", filter=Q(status__in=[Status.RESOLVED, Status.CLOSED])),
        critical=Count(
            "pk",
            filter=Q(priority="critical")
            & ~Q(status__in=[Status.RESOLVED, Status.CLOSED]),
        ),
        overdue=Count(
            "pk",
            filter=Q(resolution_due_at__lt=timezone.now())
            & ~Q(status__in=[Status.RESOLVED, Status.CLOSED]),
        ),
        first_response=Avg(
            ExpressionWrapper(
                F("first_response_at") - F("created_at"), output_field=DurationField()
            )
        ),
        resolution=Avg(
            ExpressionWrapper(
                F("resolved_at") - F("created_at"), output_field=DurationField()
            )
        ),
    )
    display_stats = [
        ("Tickets totales", stats["total"]),
        ("Abiertos", stats["open"]),
        ("Pendientes de información", stats["pending"]),
        ("Resueltos y cerrados", stats["resolved"]),
        ("Críticos activos", stats["critical"]),
        ("Vencidos", stats["overdue"]),
        ("Primera respuesta promedio", stats["first_response"]),
        ("Resolución promedio", stats["resolution"]),
    ]
    return render(
        request,
        "support/dashboard.html",
        {
            "stats": stats,
            "display_stats": display_stats,
            "filters": form,
            "by_category": qs.values("category__name")
            .annotate(total=Count("pk"))
            .order_by("-total"),
            "by_assignee": qs.values("assignee__username")
            .annotate(total=Count("pk"))
            .order_by("-total"),
            "by_period": qs.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("pk"))
            .order_by("-day")[:90],
        },
    )


@login_required
def configuration(request):
    from django.contrib.auth.models import Group
    from django.db import transaction

    from .forms import AgentForm, CategoryForm, PolicyForm
    from .models import Category, SLAPolicy, SupportAudit
    from .permissions import is_platform_admin

    if not (
        is_platform_admin(request.user)
        or (manages_support(request.user) and request.user.organization_id is None)
    ):
        raise PermissionDenied
    category_form = CategoryForm()
    agent_form = AgentForm()
    policies = SLAPolicy.objects.order_by("pk")
    policy_forms = [
        (policy, PolicyForm(instance=policy, prefix=str(policy.pk)))
        for policy in policies
    ]
    if request.method == "POST":
        kind = request.POST.get("kind")
        if kind == "category":
            instance = (
                get_object_or_404(Category, pk=request.POST["pk"])
                if request.POST.get("pk")
                else None
            )
            category_form = CategoryForm(request.POST, instance=instance)
            if category_form.is_valid():
                with transaction.atomic():
                    obj = category_form.save()
                    SupportAudit.objects.create(
                        actor=request.user,
                        action="category_configured",
                        object_label=str(obj),
                        changes={"active": obj.active},
                    )
                return redirect("support:configuration")
        elif kind == "policy":
            policy = get_object_or_404(SLAPolicy, pk=request.POST.get("pk"))
            form = PolicyForm(request.POST, instance=policy, prefix=str(policy.pk))
            if form.is_valid():
                with transaction.atomic():
                    obj = form.save()
                    SupportAudit.objects.create(
                        actor=request.user,
                        action="sla_configured",
                        object_label=str(obj),
                        changes=form.cleaned_data,
                    )
                return redirect("support:configuration")
            policy_forms = [
                (obj, form if obj.pk == policy.pk else f) for obj, f in policy_forms
            ]
        elif kind == "agent":
            if not is_platform_admin(request.user):
                raise PermissionDenied
            agent_form = AgentForm(request.POST)
            if agent_form.is_valid():
                with transaction.atomic():
                    group = Group.objects.get(name="Agentes de soporte")
                    target = agent_form.cleaned_data["user"]
                    if agent_form.cleaned_data["enabled"]:
                        target.groups.add(group)
                    else:
                        target.groups.remove(group)
                    SupportAudit.objects.create(
                        actor=request.user,
                        action="agent_permission_changed",
                        object_label=str(target.pk),
                        changes={"enabled": agent_form.cleaned_data["enabled"]},
                    )
                return redirect("support:configuration")
        else:
            raise PermissionDenied
    return render(
        request,
        "support/configuration.html",
        {
            "category_form": category_form,
            "agent_form": agent_form,
            "policy_forms": policy_forms,
            "categories": Category.objects.all(),
            "audit": SupportAudit.objects.select_related("actor")[:100],
        },
    )

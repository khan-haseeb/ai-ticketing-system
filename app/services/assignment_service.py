from app.repositories.ticket_repo import ticket_repo
from app.repositories.user_repo import user_repo
from app.repositories.project_repo import project_repo


class AssignmentService:

    async def assign_ticket(
        self,
        db,
        ticket_id,
        assignee_id,
        force=False
    ):
        ticket = await ticket_repo.get(
            db,
            ticket_id
        )

        if not ticket:
            raise Exception("Ticket not found")

        user = await user_repo.get(
            db,
            assignee_id
        )

        if not user:
            raise Exception("Assignee not found")

        is_member = await project_repo.is_member(
            db,
            ticket.project_id,
            assignee_id
        )

        if not is_member:
            raise Exception(
                "User is not part of this project"
            )

        conflict = await ticket_repo.check_assignment_conflict(
            db,
            ticket_id,
            assignee_id
        )

        if conflict and not force:
            return {
                "conflict": True,
                "ticket_id": str(ticket.id),
                "current_assignee": {
                    "id": str(conflict["current_assignee"].id),
                    "name": conflict["current_assignee"].name,
                },
                "requested_assignee": {
                    "id": str(assignee_id)
                }
            }

        updated = await ticket_repo.update(
            db,
            ticket_id,
            {"assignee_id": assignee_id}
        )

        return updated
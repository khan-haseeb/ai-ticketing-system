from app.repositories import ticket_repo


class TicketService:
    async def create_ticket(self, db, payload):
        ticket = await ticket_repo.create(
            db=db,
            data=payload
        )

        return ticket

    async def update_ticket(
        self,
        db,
        ticket_id,
        payload
    ):
        ticket = await ticket_repo.get(
            db,
            ticket_id
        )

        if not ticket:
            raise Exception("Ticket not found")

        updated = await ticket_repo.update(
            db,
            ticket_id,
            payload
        )

        return updated


ticket_service = TicketService()
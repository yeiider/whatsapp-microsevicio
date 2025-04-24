from datetime import datetime

async def sync_contact_extended(db, contact_id: str, name: str, phone: str, picture: str, organization_id: str, updated_at: datetime):
    """
    Crea un nuevo contacto extendido si no existe.
    No sobreescribe si ya fue enriquecido manualmente.
    """
    existing_contact = await db.contactextendeds.find_one({"_id": contact_id, "organization_id": organization_id})

    if not existing_contact and name:
        contact_data = {
            "contact_id": contact_id,
            "name": name,
            "phone": phone,
            "is_archived":False,
            "picture": picture,
            "organization_id": organization_id,
            "created_at": updated_at,
            "updated_at": updated_at
        }
        await db.contactextendeds.insert_one(contact_data)
        return contact_data
    else:
        return existing_contact

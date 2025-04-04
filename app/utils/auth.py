from bson import ObjectId
from fastapi import HTTPException

async def validate_organization(db, organization_id: str, token: str):
    try:
        oid = ObjectId(organization_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid organization ID format")

    organization = await db.organizations.find_one({"_id": oid, "uuid": token})
    if not organization:
        raise HTTPException(status_code=403, detail="Unauthorized webhook request")

    return organization

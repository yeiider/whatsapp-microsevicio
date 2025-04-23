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


async def get_user_organization(db, user_id: str):
    try:
        uid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await db.users.find_one({"_id": uid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    organization_id = user.get("organizationId")
    if not organization_id:
        raise HTTPException(status_code=404, detail="User has no organization assigned")

    return str(organization_id)
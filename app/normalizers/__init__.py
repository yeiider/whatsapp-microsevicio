from app.normalizers.waha import normalize_waha_message

def normalize_payload(provider: str, payload: dict):
    if provider == "waha":
        return normalize_waha_message(payload)
    elif provider == "meta":
        # Aquí se implementará en el futuro
        raise NotImplementedError("Meta provider normalization is not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: {provider}")
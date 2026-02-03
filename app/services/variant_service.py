
def generate_variants(source_text: str, count: int = 3) -> list[str]:
    """Stub generator for same-type variants."""
    return [
        f"变式题 {index + 1}：{source_text}"
        for index in range(count)
    ]

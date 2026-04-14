import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.product_matcher import ProductMatcher


def test_product_matching():
    matcher = ProductMatcher()

    # Test 1 — same product different wording
    result = matcher.combined_score(
        "Apple iPhone 15 128GB Black",
        "iPhone 15 (128 GB) - Midnight Black"
    )
    print("\nTest 1 — Same product different wording:")
    print(f"  Combined:         {result['combined_score']}")
    print(f"  Different version:{result['different_version']}")
    print(f"  Match:            {result['is_match']} <- should be True")

    # Test 2 — different products
    result2 = matcher.combined_score(
        "Apple iPhone 15 128GB Black",
        "Samsung Galaxy S24 Ultra 256GB"
    )
    print("\nTest 2 — Different products:")
    print(f"  Combined:         {result2['combined_score']}")
    print(f"  Different version:{result2['different_version']}")
    print(f"  Match:            {result2['is_match']} <- should be False")

    # Test 3 — same brand DIFFERENT model
    result3 = matcher.combined_score(
        "Apple iPhone 15 128GB Black",
        "Apple iPhone 14 128GB Black"
    )
    print("\nTest 3 — Same brand different model:")
    print(f"  Combined:         {result3['combined_score']}")
    print(f"  Different version:{result3['different_version']}")
    print(f"  Match:            {result3['is_match']} <- should be False")

    # Test 4 — debug version extraction for each candidate
    print("\nTest 4 — Find best match (debug):")
    query = "Sony WH-1000XM5 Wireless Headphones Black"
    candidates = [
        "Sony WH1000XM5 Noise Cancelling Headphones",
        "Bose QuietComfort 45 Headphones",
        "Apple AirPods Pro 2nd Generation",
        "Sony WH-1000XM4 Wireless Headphones",
    ]

    # Debug — show version numbers and filtering for each candidate
    print(f"  Query versions: {matcher.extract_version_numbers(query)}")
    for c in candidates:
        nums = matcher.extract_version_numbers(c)
        diff = matcher.is_different_version(query, c)
        print(f"  [{c[:40]}]")
        print(f"    versions={nums}  different={diff}")

    result4 = matcher.find_best_match(query, candidates)
    print(f"\n  Best match: {result4['matched_title']}")
    print(f"  Score:      {result4['score']}")
    print(f"  Correct:    {'YES' if 'XM5' in result4['matched_title'] else 'NO'}")

    # Test 5 — books debug
    print("\nTest 5 — Book title matching:")
    a = "A Light in the Attic"
    b = "A Light in the Attic (Shel Silverstein)"
    nums_a = matcher.extract_version_numbers(a)
    nums_b = matcher.extract_version_numbers(b)
    sbert = matcher.sbert_similarity(a, b)
    fuzzy = matcher.fuzzy_similarity(a, b)
    result5 = matcher.combined_score(a, b)
    print(f"  Versions A: {nums_a}")
    print(f"  Versions B: {nums_b}")
    print(f"  SBERT:    {sbert:.4f}")
    print(f"  Fuzzy:    {fuzzy:.4f}")
    print(f"  Combined: {result5['combined_score']}")
    print(f"  Match:    {result5['is_match']} <- should be True")
    print(f"  Threshold:{matcher.SBERT_THRESHOLD}")


if __name__ == "__main__":
    test_product_matching()
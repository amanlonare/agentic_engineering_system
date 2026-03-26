import argparse

from src.core.graph_store import GraphStore


def main():
    parser = argparse.ArgumentParser(description="Inspect chunks in the Graph Store.")
    parser.add_argument("--repo", help="Filter by repository name")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Limit the number of results (default: 50)",
    )
    args = parser.parse_args()

    graph = GraphStore()

    query = """
    MATCH (r:Repository)-[:CONTAINS]->(s:Source)-[:CONTAINS]->(d:Document)-[:CONTAINS]->(c:Chunk)
    """
    if args.repo:
        query += f" WHERE r.name = '{args.repo}'"

    query += " RETURN r.name, d.path, c.symbol_name, c.chunk_type LIMIT " + str(
        args.limit
    )

    print(f"🔍 Querying Graph Store (limit {args.limit})...\n")
    try:
        results = graph.execute_query(query)
        if not results:
            print("No chunks found in the Graph Store.")
            return

        print(
            f"{'REPOSITORY':<25} | {'DOCUMENT PATH':<40} | {'SYMBOL NAME':<30} | {'TYPE'}"
        )
        print("-" * 110)
        for row in results:
            repo, path, symbol, ctype = row
            # Truncate strings for display
            repo = (repo[:22] + "..") if len(repo) > 25 else repo
            short_path = (path[-37:] + "..") if len(path) > 40 else path
            symbol = (symbol[:27] + "..") if len(symbol) > 30 else symbol

            print(f"{repo:<25} | {short_path:<40} | {symbol:<30} | {ctype}")

        print(f"\n✅ Total results: {len(results)}")

    except Exception as e:
        print(f"❌ Error querying graph: {e}")


if __name__ == "__main__":
    main()

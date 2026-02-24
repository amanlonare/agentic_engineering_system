import os

from langgraph.graph import END, START, StateGraph

from src.core.state import EngineeringState
from src.core.supervisor import supervisor_node
from src.nodes.coder import coder_node
from src.nodes.growth import growth_node
from src.nodes.ops import ops_node
from src.nodes.planning import planning_node
from src.schemas import NodeName
from src.utils.logger import configure_logging

logger = configure_logging()


def build_graph(checkpointer=None):
    """
    Constructs and returns the compiled LangGraph.
    Defines the nodes, conditional routing, and edges back to the supervisor.
    """
    logger.info("Constructing the Engineering Agent graph...")

    builder = StateGraph(EngineeringState)

    # 1. Add all nodes
    builder.add_node(NodeName.SUPERVISOR, supervisor_node)
    builder.add_node(NodeName.PLANNING, planning_node)
    builder.add_node(NodeName.CODER, coder_node)
    builder.add_node(NodeName.OPS, ops_node)
    builder.add_node(NodeName.GROWTH, growth_node)

    # 2. Add edges
    # The workflow always starts at the supervisor
    builder.add_edge(START, NodeName.SUPERVISOR)

    # The supervisor uses conditional edges to route to the workers based on 'next_action'
    builder.add_conditional_edges(
        NodeName.SUPERVISOR,
        lambda state: state.next_action,
        {
            NodeName.PLANNING: NodeName.PLANNING,
            NodeName.CODER: NodeName.CODER,
            NodeName.OPS: NodeName.OPS,
            NodeName.GROWTH: NodeName.GROWTH,
            NodeName.FINISH: END,
        },
    )

    # All workers route back to the Supervisor when they are done
    for worker in [NodeName.PLANNING, NodeName.CODER, NodeName.OPS, NodeName.GROWTH]:
        builder.add_edge(worker, NodeName.SUPERVISOR)

    # 3. Compile the graph
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    # Generate a visualization of the graph
    # To run this, use: python3 -m src.core.graph
    app_graph = build_graph()
    try:
        # Generate the Mermaid PNG
        png_data = app_graph.get_graph().draw_mermaid_png()
        output_path = os.path.join(os.getcwd(), "graph.png")

        with open(output_path, "wb") as f:
            f.write(png_data)

        print(f"✅ Graph visualization saved to: {output_path}")
    except Exception as e:
        print(f"❌ Error generating visualization: {e}")
        print("Note: Ensure 'pygraphviz', 'graphviz', and 'pillow' are installed.")

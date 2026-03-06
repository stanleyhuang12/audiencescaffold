###  brainstorming - Fri Mar 6th, 2026

- Develop a storyboarding and whiteboarding system that allows teams to generate more creative ideas, connect ideas, and curate novel insights from related concepts. It is a diagramming software that supports an LLM-based system that centers human ideas and human agency and enters into an iterative loop to continue to probe, push, and explore new perspectives. 

I can think of a few ways where  can have dynamic lLM generative components: 

1. Connector Operator (find a way to connect or create a bidirectional thread, a symmetric bidirectional graph)
2. Causal Operator (find a way to link a causal mechanism, a di-graph)
3. Perspective Operator (takes many different concepts and finds ways to cluster them into different groups)
4. Seed Operator (sets a seed for an operator)
5. Generative (generates some freeform texts as users query)

```python 
node = Node(
    "Willy Wonka swept open the peppermint-striped gates of the factory with a conspiratorial grin, "
    "inviting the children into a world where rivers tasted of chocolate and every hallway "
    "seemed to hide another improbable confection.",
    "text"
)

node2 = Node(
    "Far from sugared rivers and candied dreams, Alice stepped into the silent neon streets "
    "of the Borderland, where games replaced rules and survival replaced wonder—yet she couldn’t "
    "shake the uneasy feeling that someone, somewhere, had also designed this place like a "
    "twisted kind of amusement.",
    "text"
)
```

```python
node = Node(content="Willy Wonka...", content_type="text")
node2 = Node(content="Far from sugar..", content_type="text")

seed = Seed(primer="...")

edge = Operator(nodes=[node, node2], seed=seed)
edge.process()

connector = Connector(nodes=[node, node2], seed=seed)
connector.process()

causal = Causal(nodes=[node, node2], seed=seed)
causal.process()

perspective = Perspective(nodes=[node, node2], seed=seed)
perspective.process()
```


We want to basically connect these nodes and look for ways to relate them with an Edge()? 





We can test this system by allowing a person to explore this by writing a story or trying to backfill a story. We can also test this system by allowing people and running a 20 person HCI study
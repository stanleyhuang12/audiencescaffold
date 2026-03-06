from __future__ import __annotations__
from typing import List
from litellm import completion 
from abc import ABC, abstractmethod


AVAILABLE_CONTENTS = [
    'text',
    'textbox',
    'directed-edge',
    'undirected-edge',
    'grouper',
]

class Node: 
    def __init__(self, content, content_type): 
        self.content = content
        self.content_type = content_type 
        self._validate_type()
       
        self.data = {"content": self.content, "content_type": self.content_type}
    
    def _validate_type(self): 
        if self.content_type not in AVAILABLE_CONTENTS: 
            raise ValueError(
                f"Content type {self.content_type} is not supported." \
                f"Only {AVAILABLE_CONTENTS.join(", ").strip()} is supported."
                    )
    @property 
    def _get_data(self): 
        return self.data 
    
    def __repr__(self): 
        return (f"Node(content={self.content!r}, content_type={self.content_type!r})")


node = Node(
    "Willy Wonka swept open the peppermint-striped gates of the factory with a conspiratorial grin, "
    "inviting the children into a world where rivers tasted of chocolate and every hallway "
    "seemed to hide another improbable confection.",
    "text"
)
node

class Operator: 
    """
    An operator is a structure that enables users to manipulate node(s). 
    """
    def __init__(self, nodes: List[Node]): 
        self.nodes = nodes
    
    def _prepare_prompt(self): 
        pass 
    
    @abstractmethod 
    def process(self): 
        """
        Each operator will implement their own `process` method.
        """

        pass 

class Connector(Operator):
    pass

class Causal(Operator): 
    pass 

class Perspective(Operator):
    pass


class Seed(Operator): 
    pass 

class Generative(Operator): 
    pass 
    
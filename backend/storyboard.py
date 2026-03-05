from __future__ import __annotations__


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
        
        self.data = (self.content, self.content_type)
    
    def _validate_type(self): 
        if self.content_type not in AVAILABLE_CONTENTS: 
            raise ValueError(
                f"Content type {self.content_type} is not supported." \
                f"Only {AVAILABLE_CONTENTS.join(", ").strip()} is supported."
                    )
    @property 
    def _get_data(self): 
        return self.data 



class Operator: 
    """
    An operator works as a way to manipulate two nodes. 
    """
    def __init__(self, node: Node): 
        self.node = node

class Connector(Operator):
    pass

class Causal(Operator): 
    pass 

class Cluster(Operator):
    pass


class Seed(Operator): 
    pass 

class Generative(Operator): 
    pass 
    
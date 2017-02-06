##
## Composite pattern
##

class Item(object):
    def __init__(self):
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def iterate(self, function):
        for child in self:
            function(child)

    def traverse(self, visitor):
        self.iterate(visitor.visit)

    def __iter__(self):
        return iter(self.children)



class RawValueItem(Item):
    """ The raw value is intended to be any type"""
    def __init__(self, value):
        super(RawValueItem, self).__init__()
        self.rawvalue = value

    def __str__(self):
        return str(self.rawvalue)



##
## Composite pattern
##

class Item(object):
    def __init__(self):
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def traverse(self, visitor):
        for child in self:
            visitor.visit(child)

    def __iter__(self):
        return iter(self.children)



class RawValueItem(Item):
    """ The raw value is intended to be any type"""
    def __init__(self, value):
        super(Item, self).__init__()
        self.rawvalue = value



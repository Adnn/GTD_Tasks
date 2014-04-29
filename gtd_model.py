##
## GTD logical view
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



class GtdItem(Item):
    def __init__(self, value, category, completed,
                 due_date=None, recipient=[]):
        super(GtdItem, self).__init__()
        self.completed = completed
        self.value = value
        self.category = category
        self.due_date = due_date
        self.tag_list = []

        #There should be only one plane and recipient on an item, set this way to gracefully catch data layer errors
        self.plane_list = []
        self.recipient_list = recipient

    def __repr__(self):
        return u"[{category}] {value}".format(category=self.category, value=self.value)

    def __unicode__(self):
        return u"[{category}] {value}".format(category=self.category, value=self.value)

    def pretty_print(self, indent_level=0):
        print(u"{indent}{item}".format(item=self, indent='\t'*indent_level))
        for child in self.children:
            child.pretty_print(indent_level+1)

    def append_tag(self, tag):
        self.tag_list.append(tag)



class NextAction(GtdItem):
    pass

#class TalkTo(NextAction):
#    def __init__(self, value, completed, receiver):
#        super(TalkTo, self).__init__(value, "NEXT


class Project(GtdItem):
    pass


class SimpleValue(object):
    def __init__(self, name):
        self.name = name

# Called implicitly when calling str() on collections of SimpleValue instances
    def __repr__(self):
        return self.name.encode('utf-8')

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name.encode('utf-8')

    def __eq__(self, other):
        return self.name == other.name

    def __ne__(self, other):
        return not self.__eq__(other)


class Tag(SimpleValue):
    def __init__(self, tag_name, parent=None):
        super(Tag, self).__init__(tag_name)
        self.parent = parent


class Plane(SimpleValue):
    pass


class Recipient(SimpleValue):
    pass

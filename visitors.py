from gtd_model import GtdItem, Item, NextAction, Project, Tag, Plane, Recipient

import inspect
import sys

##
## A decorator to simulate method overloading
##
class MultiMethod(object):
    def __init__(self):
        self._implementations = {}
    
    def register(self, key):
        def inner(f):
            if key in self._implementations:
                raise TypeError("Duplicate registration for %r" % key)
            self._implementations[key] = f
            return self
        return inner
    
    # 'Classic' Python's magic. see: http://stackoverflow.com/a/3296318
    def __get__(self, obj, objtype):
        """Support instance methods."""
        import functools
        return functools.partial(self.__call__, obj)

    def _get_method(self, arg_type):
        for curr_type in inspect.getmro(arg_type):
            if curr_type in self._implementations:
                return self._implementations[curr_type]
        raise KeyError

    def __call__(self, *args):
        return self._get_method(type(args[1]))(*args)

##
## Visitors
##
class Visitor(object):
    pass

class ListNextActions(Visitor):
    dispatch = MultiMethod()

    def __init__(self):
        self.next_actions = Item() 

    @dispatch.register(Item)
    def visit(self, visitee):
        visitee.traverse(self)


    @dispatch.register(NextAction)
    def visit(self, visitee):
        self.next_actions.add_child(visitee)
        visitee.traverse(self)

    def __repr__(self):
        return str(self.next_actions)

    def result(self):
        return self.next_actions
        
class PrettyPrinter(Visitor):
    dispatch = MultiMethod()

    def __init__(self):
        self.indent_level = 0

    def __indent(self):
        sys.stdout.write('\t'*self.indent_level)

    def __member_list(self, item, member_name):
        member_list = getattr(item, u'%s_list'%(member_name))
        if member_list:
            self.__indent()
            print(u' *{label}{plural}: {tags}'.format(label=member_name.upper(),
                                                      #tags=u"[" + u" ".join([unicode(member) for member in member_list]) + u"]",
                                                      tags = str(member_list).decode('utf-8'),
                                                      plural=(u'S' if len(member_list)>1 else u'')))

    @dispatch.register(Item)
    def visit(self, visitee):
        visitee.traverse(self)
    
    @dispatch.register(GtdItem)
    def visit(self, item):
        self.__indent()
        print(u"{item}".format(item=item))
        self.__member_list(item, 'tag')
        self.__member_list(item, 'plane')
        self.__member_list(item, 'recipient')

        self.indent_level += 1
        item.traverse(self)
        self.indent_level -= 1

class Addresse(Visitor):
    dispatch = MultiMethod()

    def __init__(self, addressee):
        self.addressee = addressee
        self.result_ = Item()

    @dispatch.register(Item)
    def visit(self, visitee):
        visitee.traverse(self)

    @dispatch.register(GtdItem)
    def visit(self, visitee):
        if self.addressee in visitee.recipient_list:
            self.result_.add_child(visitee)

    def result(self):
        return self.result_
        
class FilterSet(object):

    def __init__(self, visitable):
        self.collection = visitable

    def filter(self, visitor):
        visitor.visit(self.collection) 
        return FilterSet(visitor.result())


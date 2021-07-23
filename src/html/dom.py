class OrderedSet:
    def __init__(self, *args):
        self.items = []
        for arg in args:
            if arg not in self.items:
                self.items.append(arg)

    def append(self, item):
        if item not in self.items:
            self.items.append(item)

    def prepend(self, item):
        if item not in self.items:
            self.items.insert(0, item)

    def replace(self, item, replacement):
        if item in self.items:
            new_list = []
            for element in self.items:
                if element == item and element not in new_list:
                    new_list.append(replacement)
                elif element not in new_list:
                    new_list.append(element)
            self.items = new_list

    def __getitem__(self, item):
        return self.items[item]

    def __repr__(self):
        return str(self.items)


# noinspection PyMethodMayBeStatic
class Node:
    def __init__(self, parent=None):
        self.parent = parent
        self.children = OrderedSet()
        self.root = self.get_root()
        self.node_properties = self.set_properties()

    def get_root(self):
        if self.parent is None:
            return self
        else:
            return self.parent.root

    def add_child(self, child):
        if child.parent is None:
            child.parent = self
            child.root = self.get_root()
        self.children.append(child)
        return self

    def set_properties(self):
        return {}


class Document(Node):
    def set_properties(self):
        return {
            "can_change_mode": False
        }

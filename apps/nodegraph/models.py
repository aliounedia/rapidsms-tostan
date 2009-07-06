#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.db import models

# 
# A data model for simple interconnected graphs of nodes.
#
# There are two types of nodes: Sets and Leaves.
#
# The only distinction is:
# - Sets may contain other nodes (both Sets and Leaves)
# - Leaves may _not_ contain other nodes (they terminate the graph)
#
# Speaking concretely, A graph of Nodes can represent GROUPS of USERS where:
# - Groups are Sets and can contain other Groups and Users
#
# Data integrity policies/enforcement:
# - When requests a list of members for a Set, the model will break cycles.
#   So if you have Set A with itself as the only member (A<A--A contains A) asking for the
#   members of 'A' will not create an endless loop, and will return an empty list
#
#   In the case of A<B<A (A contains B contains A) A.members() returns B only
#
# ALL OTHER RULES MUST BE ENFORCED BY THE USER OF THE MODEL. 
# For example, there is no restriction on Leaves appearing in multiple Sets
# 
#

class AbstractNode(models.Model):
    """
    Abstract superclass for Nodes and NodeSets

    """

    """
    For testing only. If you want a real name, id, or any other data,
    make Node and NodeSet subclasses

    """
    debug_id = models.CharField(max_length=16,blank=True,null=True)
    

    def get_ancestors(self,max_alt=None,klass=None):
        """max_alt=None means no limit
        
           if 'klass' is a Class, downcast results

        """
        seen=set()

        if max_alt is not None:
            max_alt=int(max_alt)
            if max_alt<1:
                return
            max_alt
            
        def _recurse(node,alt):
            if node is None or \
                    (max_alt is not None and alt>max_alt) or \
                    node in seen:
                print "done"
                return

            seen.add(node)
            for a in node.get_parents():
                _recurse(a,alt+1)


        _recurse(self,0)
        seen.remove(self)
        ret=None
        if klass is not None:
            ret = [r._downcast(klass) for r in seen]
        else:
            ret = list(seen) # make a list so indexable, but order not guaranteed
        return ret

    def get_parents(self,klass=None):
        """
        The parent NodeSets this node is a member of.

        Equivalent to 'get_ancestors(max_alt=1)'

        Downcasted to 'klass' if provided (see downcast() for more info)

        """
        rents=self.parents.all()
        if klass is not None:
            return [r._downcast(klass) for r in rents]
        else:
            return rents

    def __unicode__(self):
        return self.debug_id

    def _downcast(self, klass):
        """Multiple-inherited models are weird.
           If you access a subclass from a superclass manager, you
           get an object of superclass type.

           E.g. You do aNone=Node.objects.all()[0], you will get Node classes
           even if the actual object is a subclass like a Contact.

           The 'contact' object will be availble as aNode.contact

           This method, given a target Class, will return the properly typed
           subclass.

           Usage example: aWorker=aNode.downcast(Worker)

           NOTE: If the object is not fully downcastable, it
           casts as far as possible, so return values may be of
           differing types.

           Take this obj map where '<' means inherits from:
           d<c<b<a

           If you have a set of objects (d,c,b,a), all know as 'a' type, and
           you downcast to 'd', the resulting list will be typed (d,c,b,a)

           NOTE2: PROBABLY WONT WORK WITH MULTIPLE INHERITENCE!! SO
           DON'T USE IT, IT'S DUMB ANYWAY. YOU _REALLY_ WANT duck-typing OR
           delegation OR component model instead.

           """
        # what class do I think I am?
        # e.g. 'Node'
        self_cname=self.__class__.__name__
        
        # what are all the target-class's superclasses?
        # e.g. Man<Person<Node<AbstractNode<object
        cast_cnames=[c.__name__ for c in klass.__mro__]

        # truncate list to only classes between target class and what
        # I think I am.
        # e.g. Man<Person
        cast_cnames=[cn.lower() for cn in cast_cnames[:cast_cnames.index(self_cname)]]

        # swap order for the walk
        # e.g. Person>Man
        cast_cnames.reverse()
        casted=self
        for cn in cast_cnames:
            # See if I have the Django inherited model attrib
            # and remeber that pointer
            # # self.person
            if hasattr(casted,cn):
                casted=getattr(casted,cn)
            else:
                break
        return casted
        
    class Meta:
        abstract=True


class Node(AbstractNode):
    """
    Abstract representation of a Node in the graph.
    
    Contains common properties of Set and Leaf.
    
    """

    # helpers 'cause directionality can be confusing
    def add_to_parent(self,rent):
        rent.add_children(self)

    def add_to_parents(self,*rents):
        for rent in rents:
            self.add_to_parent(rent)

    def remove_from_parent(self,rent):
        rent.remove_children(self)

    def remove_from_parents(self,*rents):
        for rent in rents:
            self.remove_from_parent(self)


class NodeSet(AbstractNode):
    """
    A node that has 'members', which is a set of nodes this node points too. 
    Named 'NodeSet' to distinguish from python type 'set'

    Because of awkwardness in mapping Python inheritence to SQL, need
    to hold 'Nodes' and 'NodeSets' in separate lists, but provide helpers
    to make this invisible to user.

    """

    _childsets = models.ManyToManyField('self',related_name='parents',symmetrical=False)
    _childleaves = models.ManyToManyField(Node,related_name='parents') 
    
    def __unicode__(self):
        """
        Prints the graph starting at this instance.

        Format is NodeSetName(subnode_set(*), subnode+)

        If nodes appear more than once in traversal, additional references are
        shown as *NodeSetName--e.g. pointer-to-NodeSetName.

        Given A->b,c,D->A, where CAPS are NodeSet and _lowers_ are Nodes, results are:

        A(D(*A),b,c)
        
        """

        buf=list()
        seen=set()
        def _recurse(node, index):
            if index>0:
                buf.append(u',')

            if node in seen:
                buf.append(u'*%s' % node.debug_id)
                return

            seen.add(node)
            buf.append(u'%s(' % node.debug_id)
            index=0
            for sub in node.childsets:
                _recurse(sub,index)
                index+=1

            leaves=u','.join([unicode(l) for l in node.childleaves])
            if len(leaves)>0:
                if index>0:
                    buf.append(u',')
                buf.append(u'%s)' % leaves)

        _recurse(self,0)

        return u''.join(buf)

    #
    # helpers because directionality is confusing
    #
    def add_to_parent(self,rent):
        rent.add_children(self)

    def add_to_parents(self,*rents):
        """
        Add this instance to the listed groups

        """
        for rent in rents:
            self.add_to_parent(rent)

    def remove_from_parent(self,rent):
        rent.remove_children(self)

    def remove_from_parents(self,*rents):
        for rent in rents:
            self.remove_from_parent(rent)

    # safe to use, but calls above should be sufficient
    def add_children(self,*sub_nodes):
        """
        Add the passed nodes to this instance as 'subnodes'
        
        Can be NodeSets or Nodes
        
        """
        for n in sub_nodes:
            # distinguish between Nodes and NodeSets
            if isinstance(n, Node):
                self._childleaves.add(n)
            elif isinstance(n, NodeSet):
                self._childsets.add(n)

    def remove_children(self, *subnodes):
        for n in subnodes:

            # distinguish between Nodes and NodeSets
            if isinstance(n, Node):
                self._childleaves.remove(n)
            elif isinstance(n, NodeSet):
                self._childsets.remove(n)

    # and some shortcut properties
    def __getchildsets(self):
        """All the direct sub-NodeSets"""
        return self._childsets.all()
    childsets=property(__getchildsets)

    def __getchildleaves(self):
        """All the direct sub-Nodes"""
        return self._childleaves.all()
    childleaves=property(__getchildleaves)

    def __getchildren(self):
        """A list of both the sub-NodeSets and sub-Nodes"""
        return self.childsets+self.childleaves
    children=property(__getchildren)

    # full graph access methods
    def flatten(self, max_depth=None,klass=None):
        """
        Flattens the graph from the given node to max_depth returning
        a set of all leaves.

        Breaks cycles.

        """
        # hold unique set of NodeSets we've visited to break cycles
        seen=set()
        leaves=set()

        if max_depth is not None:
            max_depth=int(max_depth)
            if max_depth<1:
                return leaves # empty set

        # recursive function to do the flattening
        def _recurse(nodeset, depth):
            # check terminating cases
            # - node is None (shouldn't happen but why not be safe?)                        
            # - reached max_depth
            # - seen this guy before (which breaks any cycles)
            if nodeset is None or \
                    (max_depth is not None and depth==max_depth) or \
                    nodeset in seen:
                return
            
            # ok, it's a valid nodeset, add to seen
            seen.add(nodeset)
            
            # add its childleaves to 'leaves'
            leaves.update(nodeset.childleaves)

            # recurse to its childsets
            for ns in nodeset.childsets:
                _recurse(ns, depth+1)
                
        # Now call recurse
        _recurse(self, 0)
        
        # downcast if requested and make sure returns are
        # indexable lists
        if klass is not None:
            return [l._downcast(klass) for l in leaves]
        else:
            return list(leaves)


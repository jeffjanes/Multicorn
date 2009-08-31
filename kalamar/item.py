# -*- coding: utf-8 -*-
# This file is part of Dyko
# Copyright © 2008-2009 Kozea
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kalamar.  If not, see <http://www.gnu.org/licenses/>.

"""
Base classes to create kalamar items.

You probably want to use the Item.get_item_parser method to get the parser you
need. You may also want to inherit from one of the followings so you can write
your own parsers:
- CapsuleItem
- AtomItem

Any item parser class has to have a static attribute "format" set to the format
parsed, otherwise this class will be hidden to get_item_parser.

A parser class must implement the following methods:
- _custom_parse_data(self)
- _custom_serialize(self, properties)

It must have a class attribute "format" which is name of the parsed format.

Parser classes can define an atribute "_keys" listing the name of the properties
they *need* to work well.

"""

from copy import copy
from werkzeug import MultiDict
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
    
from kalamar import parser, utils

class Item(object):
    """Abstract class, base of any item parser.
    
    You can use the Item.get_item_parser static method to get automatically the
    parser you want.

    Useful attributes:
    - properties: acts like a defaultdict. The keys are strings and the values
      are MultiDict of python objects with default value at None.
    - _access_point: where, in kalamar, is stored the item. It is an instance
      of AccessPoint.

    This class is abstract and used by AtomItem and CapsuleItem, which are
    inherited by the parsers.

    """
    
    format = None
    _keys = []

    def __init__(self, access_point, opener=StringIO, storage_properties={}):
        """Return an instance of Item.
        
        Parameters:
        - access_point: an instance of the AccessPoint class.
        - opener: a function taking no parameters and returning file-like
          object.
        - storage_properties: properties generated by the storage for this
          item.
        
        """
        self._opener = opener
        self._stream = None
        self._access_point = access_point
        
        self.aliases = dict(self._access_point.parser_aliases)
        self.aliases.update(self._access_point.storage_aliases)
        self.aliases_rev = dict((b,a) for (a,b) in enumerate(self.aliases))
        
        self.properties = ItemProperties(self, storage_properties)
    
    @staticmethod
    def create_item(access_point, properties):
        """Return a new item instance.
        
        Parameters:
            - "access_point": instance of the access point where the item
              will be reachable (after saving).
            - "properties": dictionnary or MultiDict of the item properties.
              These properties must be coherent with what is defined for the
              access point.
        
        Fixture
        >>> from _test.corks import CorkAccessPoint, cork_opener
        >>> ap = CorkAccessPoint()
        >>> properties = {}
        
        Test
        >>> item = Item.create_item(ap, properties)
        >>> #assert item.format == ap.parser_name
        >>> #assert isinstance(item, Item)
        
        """
        
        parser.load()
        
        storage_properties = dict((name, None) for name
                                  in access_point.get_storage_properties())
        
        item = Item.get_item_parser(access_point,
                                    storage_properties = storage_properties)
        
        # ItemProperties copies storage_properties in storage_properties_old
        # by default, but this is a nonsens in the case of a new item.
        item.properties.storage_properties_old = {}
                
        # Needed because there is no binary data to parse properties from. We
        # set them manually.
        item.properties._loaded = True
        
        # Some parsers may need the "_content" property in their "serialize"
        # method.
        if '_content' not in properties:
            properties['_content'] = ''
        
        for name in properties:
            item.properties[name] = properties[name]
        
        return item
        
        # TODO: Check if all storage/parser properties have been set ?
        #       Is it even possible ?
        
        
    
    @staticmethod
    def get_item_parser(access_point, opener=StringIO, storage_properties={}):
        """Return an appropriate parser instance for the given format.
        
        Your kalamar distribution should have, at least, a parser for the
        "binary" format.
        
        >>> from _test.corks import CorkAccessPoint, cork_opener
        >>> ap = CorkAccessPoint()
        >>> ap.parser_name = 'binary'
        >>> Item.get_item_parser(ap, cork_opener, {"artist": "muse"})
        ...  # doctest: +ELLIPSIS
        <kalamar.item.AtomItem object at 0x...>
        
        An invalid format will raise a ValueError:
        >>> ap.parser_name = 'I do not exist'
        >>> Item.get_item_parser(ap, cork_opener)
        Traceback (most recent call last):
        ...
        ParserNotAvailable: Unknown parser: I do not exist
        
        """

        parser.load()
        
        if access_point.parser_name is None:
            return Item(access_point, None, storage_properties)
        
        for subclass in utils.recursive_subclasses(Item):
            if getattr(subclass, 'format', None) == access_point.parser_name:
                return subclass(access_point, opener, storage_properties)
        
        raise utils.ParserNotAvailable('Unknown parser: ' +
                                       access_point.parser_name)

    @property
    def encoding(self):
        """Return the item encoding.

        Return the item encoding, based on what the parser can know from
        the item data or, if unable to do so, on what is specified in the
        access_point.

        """
        return self._access_point.default_encoding
    
    def serialize(self):
        """Return the item serialized into a string."""
        # Remove aliases
        properties = dict((name, self.properties[name]) for name
                          in self.properties.keys_without_aliases())
        return self._custom_serialize(properties)
    
    def _custom_serialize(self, properties):
        """Serialize item from its properties, return a data string.

        This method has to be overriden.

        This method must not worry about aliases, must not modify "properties",
        and must just return a string.

        """
        return ''
    
    def _parse_data(self):
        """Call "_custom_parse_data" and do some stuff to the result."""

        self._open()
        prop = self._custom_parse_data()
        self.properties.update_parser_properties(prop)

    def _custom_parse_data(self):
        """Parse properties from data, return a dictionnary.
        
        This method has to be extended.

        This method must not worry about aliases, must not modify "properties",
        and must just use super() and update and return the MultiDict.

        """
        return MultiDict()
    
    def _open(self):
        """Open the stream when called for the first time.
        
        >>> from _test.corks import CorkAccessPoint, cork_opener
        >>> ap = CorkAccessPoint()
        >>> item = Item(ap, cork_opener, {'toto': 'ToTo'})
        
        >>> item._stream
        >>> item._open()
        >>> stream = item._stream
        >>> print stream # doctest: +ELLIPSIS
        <open file '...kalamar/_test/toto', mode 'r' at ...>
        >>> item._open()
        >>> stream is item._stream
        True
        
        """
        if self._stream is None and self._opener is not None:
            self._stream = self._opener()
    
    def content_modified(self):
        return self.properties.parser_content_modified
    
    def filename(self):
        """
        If the item is stored in a file, return it’s path/name.
        Otherwise, return None
        """
        if hasattr(self._access_point, 'filename_for'):
            return self._access_point.filename_for(self)

class AtomItem(Item):
    """An indivisible block of data.
    
    Give access to the binary data.
    
    """
    
    format = 'binary'
    
    def read(self):
        """Alias for properties["_content"]."""
        return self.properties["_content"]

    def write(self, value):
        """Alias for properties["_content"] = value."""
        self.properties["_content"] = value
    
    def _custom_parse_data(self):
        """Parse the whole item content."""
        properties = super(AtomItem, self)._custom_parse_data()
        properties['_content'] = self._stream.read()
        return properties
        
    def _custom_serialize(self, properties):
        """Return the item content."""
        return properties['_content']

class CapsuleItem(Item):
    """An ordered list of Items (atoms or capsules).

    This is an abstract class.

    """
    @property
    def subitems(self):
        if not hasattr(self, '_subitems'):
            self._subitems = utils.ModificationTrackingList(
                self._load_subitems())
        return self._subitems
        
    def _load_subitems(self):
        raise NotImplementedError("Abstract class")

class ItemProperties(MultiDict):
    """MultiDict with a default value, used as a properties storage.

    You have to give a reference to the item to the constructor. You can force
    some properties to a value giving a dictionnary as "storage_properties"
    argument.
    
    >>> from _test.corks import CorkItem, CorkAccessPoint
    >>> item = CorkItem(CorkAccessPoint(),
    ...                 storage_properties={'a': 'A', 'b': 'B'})
    >>> prop = item.properties
    
    ItemProperties works as a dictionnary:
    >>> prop['cork_prop']
    'I am a cork prop'
    
    But it can contais multiple values:
    >>> prop.getlist('cork_prop')
    ['I am a cork prop', 'toto', 'tata']
    
    This key has been forced with "storage_properties":
    >>> prop['b']
    'B'
    
    You can modifie content and know if the item's data has been modified:
    >>> prop.parser_content_modified
    False
    >>> prop['cork_prop'] = 'new value'
    >>> prop['cork_prop']
    'new value'
    >>> prop.parser_content_modified
    True
    
    Storage properties can be accessed separately by a dictionnary:
    >>> prop.storage_properties
    {'a': 'A', 'b': 'B'}
    
    If a storage property has been changed, the old value is still reachable:
    >>> prop['b'] = 'toto'
    >>> prop.storage_properties_old
    {'a': 'A', 'b': 'B'}
    
    But the original value is not changed:
    >>> super(ItemProperties, prop).__getitem__('b')
    "item's b"
    
    Return None if the key does not exist:
    >>> prop['I do not exist']
    
    CorkItem has an alias "I am aliased" -> "I am not aliased":
    >>> prop['I am aliased']
    'value of: I am not aliased'
    >>> prop['I am not aliased']
    'value of: I am not aliased'
    
    Keys with aliases can be known with
    >>> prop.keys()
    ['a', 'b', '_content', 'cork_prop', 'I am not aliased', 'I am aliased']
    
    Or without aliases
    >>> prop.keys_without_aliases()
    ['cork_prop', 'I am not aliased', 'b', 'a', '_content']
    
    """
    
    def __init__(self, item, storage_properties={}):
        """Load item properties.

        The "storage_properties" argument is a dictionnary used to set default
        values for some properties.

        For performance purpose, note that the load is lazy: calling this
        function does not really load the item in memory.
        """
        # Internal values set for lazy load
        self._item = item
        self._loaded = False
        
        # Up-to-date properties
        self.storage_properties = storage_properties
        # Properties set before last synchronizing on storage
        self.storage_properties_old = copy(storage_properties)
        self['_content'] = ''
        self.parser_content_modified = False
    
    def parser_keys(self):
        return list(self)
    
    def keys(self):
        keys = set(self.keys_without_aliases())
        keys.update(self._item.aliases.keys())
        return list(keys)
    
    def keys_with_aliases(self):
        # TODO test
        return self._item.aliases.keys()
    
    def keys_without_aliases(self):
        keys = set(self)
        keys.update(self.storage_properties.keys())
        return list(keys)
    
    def values(self):
        # TODO test
        return [self[key] for key in self.keys_without_aliases()]
    
    @property
    def aliased_storage_property(self):
        # TODO test
        return dict(
            (prop, self[prop]) 
            for prop, aliased in self._item.aliases.items()
            if aliased in self.storage_properties
        )

    
    def update_parser_properties(self, properties):
        pkeys = self.parser_keys()
        # Hum hum
        if not self._loaded and \
           len(super(ItemProperties, self).__getitem__('_content')) == 0:
            pkeys.remove('_content')
        for key in properties:
            # If the property is not already manually set by user.
            if True or key not in pkeys:
                super(ItemProperties, self).__setitem__(key, properties[key])

    def __getitem__(self, key):
        """Return the item "key" property."""
        # Aliasing
        key = self._item.aliases.get(key, key)

        if key in self.storage_properties.keys():
            return self.storage_properties[key]

        # Lazy load: load item only when needed
        if not self._loaded:
            self._item._parse_data()
            self._loaded = True            

        try:
            return super(ItemProperties, self).__getitem__(key)
        except KeyError:
            return None
    
    # Allow item.properties.prop_name syntax
    __getattr__ = __getitem__
    
    def __setitem__(self, key, value):
        """Set the item "key" property to "value"."""
        # Aliasing
        key = self._item.aliases.get(key, key)
        if key in self.storage_properties.keys():
            self.storage_properties[key] = value
        else:
            super(ItemProperties, self).__setitem__(key, value)
            self.parser_content_modified = True

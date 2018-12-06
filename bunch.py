# from the python cookbook

class Bunch(object):
    def __init__(self, *args, **kwds):
        if len(args) == 1:
            if not isinstance(args[0], Bunch):
                raise TypeError("can only initialize Bunch with another Bunch object or keyword arguments, not with a '{t}'".format(t = type(self)))
            self.__dict__.update(args[0].__dict__)
        elif len(args) > 1:
            raise TypeError("can only initialize Bunch with one Bunch object or keyword arguments".format(t = type(self)))
        self.__dict__.update(kwds)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)

    def __cmp__(self, other):
        if not isinstance(other, Bunch):
            return cmp(type(self), type(other))
        return cmp(self.__dict__, other.__dict__)

    def __hash__(self):
        raise TypeError("unhashable type: '{t}'".format(t = type(self)))

    def members(self):
        return self.__dict__;

class Hashable_Bunch(Bunch):
    def __init__(self, *args, **kwds):
        super(Hashable_Bunch, self).__init__(*args, **kwds)
        # make sure all arguments are hashable
        hash(self)

    def __setattr__(self, attr, value):
        raise TypeError("immutable type: '{t}'".format(t = type(self)))

    def __hash__(self):
        return hash(tuple(self.__dict__.items()))

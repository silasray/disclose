from logging import getLogger
from weakref import WeakKeyDictionary, ref, WeakValueDictionary
import math
from functools import partial
import itertools
from types import MethodType
import inspect
from traceback import format_tb, format_stack


class VerificationSession(object):
    
    logger = default_logger = getLogger('test.validation')
    
    # staticmethod   converted to static after reference in __init__
    def default_message_formatter(result, description, annotation):
        
        return '::VERIFICATION ' + ('PASSED' if result else 'FAILED') + '::\n' + (annotation + '\n' if annotation else '') + description
    
    # staticmethod   converted to static after reference in __init__
    def default_block_handler(result, *args):
        
        # if 1 arg, assume it's a message, if 2 args, assume it's a result and annotation
        if len(args) == 1:
            message = args[0]
        elif len(args) == 2:
            message = VerificationSession.default_message_formatter(result, *args)
        else:
            raise TypeError('default_block_handler takes a result (must be truth-testable) and 1 or 2 strings.')
        assert result, message
    
    def context_exit_handler(self, exc_type, exc_value, traceback):
        
        message = []
        if exc_type == AssertionError:
            self.logger.debug(''.join(format_tb(traceback)))
            message.append('Assertion failed: %s' % exc_value.message)
        if self.failures:
            message.append('Verification failed.')
        assert not message, '\n'.join(message)
    
    def __init__(self, message_formatter=default_message_formatter,
                 block_handler=default_block_handler, logger=None,
                 context_exit_handler=None):
        
        self.failures = []
        self.block_handler = block_handler
        self.message_formatter = message_formatter
        if context_exit_handler:
            self.context_exit_handler = MethodType(context_exit_handler, self)
        if logger:
            self.logger = logger
    
    default_block_handler = staticmethod(default_block_handler)
    default_message_formatter = staticmethod(default_message_formatter)
    
    def __call__(self, result, annotation='', blocking=False):
        
        stack = inspect.stack()
        result_meta = OperandMetadata.for_all(result)[0]
        result_real = result_meta.operand if result_meta else result
        dump_values = []
        if result_meta:
            if result_meta.description:
                description = result_meta.description
            else:
                description = result_real
            for component in result_meta.components:
                try:
                    dump_value = '{} = {}'.format(component.description, component.operand)
                except Exception:
                    pass
                else:
                    dump_values.append(dump_value)
        else:
            description = str(result_real)
        message = self.message_formatter(result, description, annotation)
        if result:
            self.logger.info(message)
            dump_value_writer = self.logger.debug
        else:
            self.failures.append((result, description, annotation, stack))
            self.logger.error(message)
            dump_value_writer = self.logger.info
        if dump_values:
            dump_value_writer('\n'.join(dump_values))
        if not result:
            if blocking:
                self.block_handler(result, message)
            self.logger.debug(''.join(format_stack(stack[1][0])))
            #self.logger.debug('\n'.join('{1} line {2} in {3}'.format(*frame) for frame in stack))
        return result
    
    def __nonzero__(self):
        
        return not self.failures
    
    def __enter__(self):
        
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        
        return self.context_exit_handler(exc_type, exc_value, traceback)


class OperandMetadata(object):
    
    _for = {}
    
    def __init__(self, operand, description, wrapper, components=None):
        
        self.operand = operand
        self.description = description
        self.wrapper = wrapper
        self.__class__._for[id(wrapper)] = self
        self.components = components if components else []
    
    @property
    def wrapper(self):
         
        return self._wrapper()
     
    @wrapper.setter
    def wrapper(self, value):
        
        def del_callback(wrapper):
            
            try:
                del self.__class__._for[id(wrapper)]
            except:
                pass
        
        self._wrapper = ref(value, partial(del_callback, value))
    
    @classmethod
    def for_all(cls, *operands):
        
        out = []
        for operand in operands:
            try:
                out.append(cls._for[id(operand)])
            except (KeyError, TypeError):
                out.append(None)
        return out
    
    @classmethod
    def real_operands(cls, *operands):
        
        metas = cls.for_all(*operands)
        return [meta.operand if meta else operand for meta, operand in zip(metas, operands)]
    
    @classmethod
    def for_(cls, operand):
        
        #print 'retrieve %d' % id(operand)
        meta = cls._for[id(operand)]
        #print 'retrieval meta %d' % id(meta)
        if meta.wrapper is operand:
            return meta
        else:
            del cls._for[id(operand)]
            raise KeyError(operand)


def description_helper(template, left_op, left_meta, right_op, right_meta):
    
    if left_meta and left_meta.description:
        left = left_meta.description
    else:
        left = str(left_op)
    if right_meta and right_meta.description:
        right = right_meta.description
    else:
        right = str(right_op)
    return template.format(right=right, left=left)

def binary_op_helper(description_template, left, right):
    
    left_meta, right_meta = OperandMetadata.for_all(left, right)
    right_left, right_real = OperandMetadata.real_operands(left, right)
    description = description_helper(description_template,
                                     right_left, left_meta,
                                     right_real, right_meta)
    return right_left, left_meta, right_real, right_meta, description


class OperandWrapperItertor(object):
    
    def __init__(self, operand, description, components=None):
        
        self.operand_iterator = iter(operand)
        self.description = description
        self.components = components if components else []
        self.counter = -1
    
    def __iter__(self):
        
        return self
    
    def next(self):
        
        self.counter += 1
        next_value = OperandMetadata.real_operands(self.operand_iterator.next())[0]
        if self.description:
            description = self.description + ' '
        else:
            description = ''
        description += self.counter
        return OperandWrapper(next_value, description, self.components)


class OperandWrapper(object):
    
    def __init__(self, *args, **kwargs):
        
        # First call to __init__ on an instance creates it
        try:
            meta = OperandMetadata.for_(self)
        except (KeyError, TypeError):
            # Args composed of operand and description
            try:
                operand, description = args[:2]
                try:
                    components = args[2]
                except IndexError:
                    components = []
            except (TypeError, IndexError, ValueError):
                operand = args[0]
                description = operand.__class__.__name__
                components = []
            # Attempt to unwrap the operand, so we don't nest wrappers
            try:
                operand = OperandMetadata.for_(operand).operand
            except(KeyError, TypeError, AttributeError):
                pass
            OperandMetadata(operand, description, self, components)
        else:
            meta.operand.__init__(meta.operand, *args, **kwargs)
    
    #### ATTRIBUTE ACCESS
    
    def __getattribute__(self, name):
        
        #print id(self)
        meta = OperandMetadata.for_(self)
        description = meta.description + '.' + name
        attr = OperandMetadata.real_operands(getattr(meta.operand, name))[0]
        return OperandWrapper(attr, description, meta.components + [meta])
    
    def __setattr__(self, name, value):
        
        value = OperandMetadata.real_operands(value)[0]
        setattr(OperandMetadata.for_(self).operand, name, value)
    
    def __delattr__(self, name):
        
        OperandMetadata.for_(self).operand.__delattr__(name)
    
    #### SEQUENCE INTERFACE
    
    def __len__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'len(' + meta.description if meta.description else meta.operand + ')'
        length = len(meta.operand)
        return OperandWrapper(length, description, meta.components + [meta])
    
    def __getitem__(self, key):
        
        meta = OperandMetadata.for_(self)
        if isinstance(key, basestring):
            description = meta.description + "['" + key + "']"
        else:
            description = meta.description + '[' + str(key) + ']'
        attr = OperandMetadata.real_operands(meta.operand[key])[0]
        return OperandWrapper(attr, description, meta.components + [meta])
    
    def __setitem__(self, key, value):
        
        value = OperandMetadata.real_operands(value)[0]
        OperandMetadata.for_(self).operand[key] = value
    
    def __delitem__(self, key):
        
        OperandMetadata.for_(self).operand[key].__delitem__(key)
    
    def __iter__(self):
        
        meta = OperandMetadata.for_(self)
        return OperandWrapperItertor(meta.operand, meta.description, meta.components + [meta])
    
    def __contains__(self, value):
        
        meta = OperandMetadata.for_(self)
        value_meta = OperandMetadata.for_all(value)[0]
        if value_meta:
            value_real = value_meta.operand
            if value_meta.description:
                value_description = value_meta.description
            else:
                value_description = value_meta.operand
        else:
            value_real = value
            value_description = str(value)
        description = '' + value_description + ' in ' + meta.description if meta.description else meta.operand
        result = value_real in meta.operand
        return OperandWrapper(result, description, meta.components + [meta])
    
    def __reversed__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'reversed(' + meta.description if meta.description else meta.operand + ')'
        reversed_ = reversed(meta.operand)
        return OperandWrapper(reversed_, description, meta.components + [meta])
    
    #### CALLABLE INTERFACE
    
    def __call__(self, *args, **kwargs):
        
        self_meta = OperandMetadata.for_(self)
        self_real = self_meta.operand
        args_real = OperandMetadata.real_operands(*args)
        args_data = zip(args_real, OperandMetadata.for_all(*args))
        args_components = list(itertools.chain(*[arg.components for arg, meta in args_data if meta]))
        kwargs_names = []
        kwargs_values = []
        for name, value in kwargs.iteritems():
            kwargs_names.append(name)
            kwargs_values.append(value)
        kwargs_real = OperandMetadata.real_operands(*kwargs_values)
        kwargs_data = zip(kwargs_real, OperandMetadata.for_all(*kwargs_values))
        kwargs_components = list(itertools.chain(*[kwarg.components for kwarg, meta in kwargs_data if meta]))
        args_description = ', '.join(meta.description if meta and meta.description else str(real) for real, meta in args_data)
        kwargs_description = ', '.join('{}={}'.format(name, meta.description if meta and meta.description else str(real))
                                       for name, (real, meta) in zip(kwargs_names, kwargs_data))
        description = (self_meta.description + '(' + args_description
                       + (', ' if args_description and kwargs_description else '') + kwargs_description + ')')
        result = self_real(*args_real, **dict(zip(kwargs_names, kwargs_real)))
        return OperandWrapper(result, description, self_meta.components + args_components + kwargs_components + [self_meta])
    
    #### HASHING
    
    def __hash__(self):
        
        try:
            meta = OperandMetadata.for_(self)
        except (KeyError, TypeError):
            meta = None
        # Should only hit this condition if hashing to insert on OperandMetadata.for_ in OperandWrapper.__init__
        if not (meta and hasattr(meta, 'operand')):
            return id(self)
        else:
            # Makes it so hashing values won't give nice log output, but otherwise we enter an infinite
            # hashing loop.
            return hash(meta.operand)
#             value = hash(meta.operand)
#             if not (hasattr(meta, 'description') and meta.description):
#                 description = meta.operand
#             else:
#                 description = meta.description
#             description = 'hash(' + description + ')'
#             return OperandWrapper(value, description)
    
    #### CONTEXT MANAGER INTERFACE
    
    def __enter__(self):
        
        meta = OperandMetadata.for_(self)
        return meta.operand.__enter__()
    
    def __exit__(self, *args, **kwargs):
        
        meta = OperandMetadata.for_(self)
        return meta.operand.__exit__(*args, **kwargs)
    
    #### BINARY OPERATORS (NON-COMPARISON)
    
    def __add__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) + ({right})',
                                                                                     self, other)
        result_value = self_real + other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __sub__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) - ({right})',
                                                                                     self, other)
        result_value = self_real - other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __mul__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) * ({right})',
                                                                                     self, other)
        result_value = self_real * other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __div__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) / ({right})',
                                                                                     self, other)
        result_value = self_real / other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __floordiv__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) // ({right})',
                                                                                     self, other)
        result_value = self_real // other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __mod__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) % ({right})',
                                                                                     self, other)
        result_value = self_real / other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __pow__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) ** ({right})',
                                                                                     self, other)
        result_value = self_real ** other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    #### BITWISE BINARY OPERATORS
    
    def __lshift__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) << ({right})',
                                                                                     self, other)
        result_value = self_real << other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rshift__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) >> ({right})',
                                                                                     self, other)
        result_value = self_real >> other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __and__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) & ({right})',
                                                                                     self, other)
        result_value = self_real & other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __or__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) | ({right})',
                                                                                     self, other)
        result_value = self_real | other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __xor__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) ^ ({right})',
                                                                                     self, other)
        result_value = self_real ^ other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    #### REFLECTED BINARY OPERATORS (NON-COMPARISON)
    
    def __radd__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) + ({right})',
                                                                                     other, self)
        result_value = other_real + self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rsub__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) - ({right})',
                                                                                     other, self)
        result_value = other_real - self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rmul__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) * ({right})',
                                                                                     other, self)
        result_value = other_real * self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rdiv__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) / ({right})',
                                                                                     other, self)
        result_value = other_real / self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rfloordiv__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) // ({right})',
                                                                                     other, self)
        result_value = other_real // self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rmod__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) % ({right})',
                                                                                     other, self)
        result_value = other_real % self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rpow__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) ** ({right})',
                                                                                     other, self)
        result_value = other_real ** self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    #### REFLECTED BITWISE BINARY OPERATORS
    
    def __rlshift__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) << ({right})',
                                                                                     other, self)
        result_value = other_real << self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rrshift__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) >> ({right})',
                                                                                     other, self)
        result_value = other_real >> self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rand__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) & ({right})',
                                                                                     other, self)
        result_value = other_real & self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __ror__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) | ({right})',
                                                                                     other, self)
        result_value = other_real | self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __rxor__(self, other):
        
        other_real, other_meta, self_real, self_meta, description = binary_op_helper('({left}) ^ ({right})',
                                                                                     other, self)
        result_value = other_real ^ self_real
        metas = []
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        metas.extend(self_meta.components)
        metas.append(self_meta)
        return OperandWrapper(result_value, description, metas)
    
    #### BINARY EQUALITY OPERATORS
    
    def __eq__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) == ({right})',
                                                                                     self, other)
        result_value = self_real == other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __ne__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) != ({right})',
                                                                                     self, other)
        result_value = self_real != other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __gt__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) > ({right})',
                                                                                     self, other)
        result_value = self_real > other_real
        metas = [self_meta]
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __ge__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) >= ({right})',
                                                                                     self, other)
        result_value = self_real >= other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __lt__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) < ({right})',
                                                                                     self, other)
        result_value = self_real < other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    def __le__(self, other):
        
        self_real, self_meta, other_real, other_meta, description = binary_op_helper('({left}) <= ({right})',
                                                                                     self, other)
        result_value = self_real <= other_real
        metas = self_meta.components + [self_meta]
        if other_meta:
            metas.extend(other_meta.components)
            metas.append(other_meta)
        return OperandWrapper(result_value, description, metas)
    
    #### AUGMENTED ASSIGNMENT BINARY OPERATORS
    
    def __iadd__(self, other):
        
        return self + other
    
    def __isub__(self, other):
        
        return self - other
    
    def __imul__(self, other):
        
        return self * other
    
    def __idiv__(self, other):
        
        return self / other
    
    def __ifloordiv__(self, other):
        
        return self // other
    
    def __imod__(self, other):
        
        return self % other
    
    def __ipow__(self, other):
        
        return self ** other
    
    def __ilshift__(self, other):
        
        return self << other
    
    def __irshift__(self, other):
        
        return self >> other
    
    def __iand__(self, other):
        
        return self & other
    
    def __ior__(self, other):
        
        return self | other
    
    def __ixor__(self, other):
        
        return self ^ other
    
    #### DESCRIPTOR PROTOCOL
    # TODO: Make this return new proxies
    # pretty obscure usage, so left undone for now
    
    ### TRUTH TESTING
    
    def __nonzero__(self):
        
        meta = OperandMetadata.for_(self)
        # __nonzero__ return value explicitly type checked for bool or int, so can't do what
        # we want here...
        return bool(meta.operand)
#         description = 'bool(' + meta.description if meta.description else meta.operand + ')'
#         return OperandWrapper(int(bool(meta.operand)), description)
    
    #### REPRESENTATION/CASTING
    
    def __str__(self):
        
         meta = OperandMetadata.for_(self)
         return str(meta.operand)
#         description = 'str(' + meta.description if meta.description else meta.operand + ')'
#         return StrOperandWrapper(str(meta.operand), description, meta.components + [meta])
    
    def __repr__(self):
        
        meta = OperandMetadata.for_(self)
        return meta.operand.__repr__()
    
    def __unicode__(self):
        
        meta = OperandMetadata.for_(self)
        return unicode(meta.operand)
#         description = 'unicode(' + meta.description if meta.description else meta.operand + ')'
#         return UnicodeOperandWrapper(unicode(meta.operand), description, meta.components + [meta])
    
    def __format__(self, format_string):
        
        meta = OperandMetadata.for_(self)
        return format_string.format(meta.operand)
#         description = ('format(' + meta.description if meta.description else meta.operand + ','
#                        + format_string)
#         return OperandWrapper(format(meta.operand, format_string), description, meta.components + [meta])
    
    def __dir__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'dir(' + meta.description if meta.description else meta.operand + ')'
        return OperandWrapper(dir(meta.operand), description, meta.components + [meta])
    
    def __int__(self):
        
        meta = OperandMetadata.for_(self)
        return int(meta.operand)
#         description = 'int(' + meta.description if meta.description else meta.operand + ')'
#         return IntOperandWrapper(int(meta.operand), description, meta.components + [meta])
    
    def __long__(self):
        
        meta = OperandMetadata.for_(self)
        return long(meta.operand)
#         description = 'long(' + meta.description if meta.description else meta.operand + ')'
#         return LongOperandWrapper(long(meta.operand), description, meta.components + [meta])
    
    def __float__(self):
        
        meta = OperandMetadata.for_(self)
        return float(meta.operand)
#         description = 'float(' + meta.description if meta.description else meta.operand + ')'
#         return FloatOperandWrapper(float(meta.operand), description, meta.components + [meta])
    
    def __complex__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'complex(' + meta.description if meta.description else meta.operand + ')'
        return OperandWrapper(complex(meta.operand), description, meta.components + [meta])
    
    def __oct__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'oct(' + meta.description if meta.description else meta.operand + ')'
        return OperandWrapper(oct(meta.operand), description, meta.components + [meta])
    
    def __hex__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'hex(' + meta.description if meta.description else meta.operand + ')'
        return OperandWrapper(hex(meta.operand), description, meta.components + [meta])
    
    def __index__(self):
        
        return OperandMetadata.for_(self).operand.__index__()
    
    def __trunc__(self):
        
        meta = OperandMetadata.for_(self)
        description = 'math.trunc(' + meta.description if meta.description else meta.operand + ')'
        return OperandWrapper(math.trunc(meta.operand), description, meta.components + [meta])
    
    def __coerce__(self, other):
        
        meta = OperandMetadata.for_(self)
        other_real = OperandMetadata.for_all(other)
        return meta.operand.__coerce__(other_real)


# class OperandWrapperMetaclass(type):
#     
#     def __instancecheck__(cls, instance):
#         
#         return isinstance(instance, cls._proxy_for)
#     
#     def __subclasscheck__(cls, instance):
#         
#         return issubclass(instance, cls._proxy_for)
# 
# def _make(name, proxy_for):
#     
#     return OperandWrapperMetaclass(name, (OperandWrapper, proxy_for), {'_proxy_for' : proxy_for, '__class__' : proxy_for})
# 
# StrOperandWrapper = _make('StrOperandWrapper', str)
# UnicodeOperandWrapper = _make('UnicodeOperandWrapper', unicode)
# IntOperandWrapper = _make('IntOperandWrapper', int)
# LongOperandWrapper = _make('LongOperandWrapper', long)
# FloatOperandWrapper = _make('FloatOperandWrapper', float)

import disclose.patch_json

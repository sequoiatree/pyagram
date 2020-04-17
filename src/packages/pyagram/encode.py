import inspect

from . import pyagram_element
from . import pyagram_types
from . import utils

class Encoder:
    """
    """

    def __init__(self, num_lines, lambdas_by_line):
        self.num_lines = num_lines
        self.lambdas_by_line = lambdas_by_line

    def reference_snapshot(self, object, memory_state, **kwargs):
        """
        <summary> # snapshot a reference to a value (may be a primitive or referent type)

        :param object:
        :param memory_state:
        :return:
        """
        # TODO: memory_state is not used in this function, so it shouldn't be a param.
        if 0 < len(kwargs):
            return kwargs
        elif pyagram_types.is_primitive_type(object):
            return repr(object) if isinstance(object, str) else str(object)
        else:
            return id(object)

    def object_snapshot(self, object, memory_state):
        """
        <summary> # snapshot a value (may be a referent type only)

        :param object:
        :param memory_state:
        :return:
        """
        object_type = type(object)
        if object_type in pyagram_types.FUNCTION_TYPES:
            is_lambda = object.__name__ == '<lambda>'
            if is_lambda:
                lineno, number = utils.unpair_naturals(object.__code__.co_firstlineno, max_x=self.num_lines)
            parameters, slash_arg_index, has_star_arg = [], None, False
            for i, parameter in enumerate(inspect.signature(object).parameters.values()):
                if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                    slash_arg_index = i + 1
                elif parameter.kind is inspect.Parameter.VAR_POSITIONAL:
                    has_star_arg = True
                elif parameter.kind is inspect.Parameter.KEYWORD_ONLY and not has_star_arg:
                    parameters.append({
                        'name': '*',
                        'default': None,
                    })
                    has_star_arg = True
                parameters.append({
                    'name': str(parameter) if parameter.default is inspect.Parameter.empty else str(parameter).split('=', 1)[0],
                    'default': None if parameter.default is inspect.Parameter.empty else self.reference_snapshot(parameter.default, memory_state),
                })
            if slash_arg_index is not None:
                parameters.insert(slash_arg_index, {
                    'name': '/',
                    'default': None,
                })
            encoding = 'function'
            snapshot = {
                'name': object.__name__,
                'lambda_id':
                    {
                        'lineno': lineno,
                        'number': number,
                        'single': len(self.lambdas_by_line[lineno]) <= 1,
                    }
                    if is_lambda
                    else None,
                'parameters': parameters,
                'parent': repr(memory_state.function_parents[object]),
            }
        elif object_type in pyagram_types.BUILTIN_FUNCTION_TYPES:
            encoding = 'builtin_function'
            snapshot = {
                'name': object.__name__,
            }
        elif object_type in pyagram_types.ORDERED_COLLECTION_TYPES:
            encoding = 'ordered_collection'
            snapshot = {
                'type': object_type.__name__,
                'elements': [
                    self.reference_snapshot(item, memory_state)
                    for item in object
                ],
            }
        elif object_type in pyagram_types.UNORDERED_COLLECTION_TYPES:
            encoding = 'unordered_collection'
            snapshot = {
                'type': object_type.__name__,
                'elements': [
                    self.reference_snapshot(item, memory_state)
                    for item in object
                ],
            }
        elif object_type in pyagram_types.MAPPING_TYPES:
            encoding = 'mapping'
            snapshot =  {
                'type': object_type.__name__,
                'items': [
                    [self.reference_snapshot(key, memory_state), self.reference_snapshot(value, memory_state)]
                    for key, value in object.items()
                ],
            }
        elif object_type in pyagram_types.ITERATOR_TYPES:
            encoding = 'iterator'
            snapshot = NotImplemented # TODO
        elif object_type in pyagram_types.GENERATOR_TYPES:
            encoding = 'generator'
            snapshot = NotImplemented # TODO
            # TODO: Probably make use of `gi_frame` in the `inspect` module.
        elif object_type is pyagram_element.PyagramClassFrame:
            encoding = 'class_frame'
            snapshot = {
                'is_curr_element': False,
                'name': object.frame.f_code.co_name,
                'parents': object,
                'bindings': {
                    key: self.reference_snapshot(value, memory_state)
                    for key, value in object.frame.f_locals.items()
                    if key not in pyagram_element.PyagramClassFrame.HIDDEN_BINDINGS
                },
                'return_value': None,
                'flags': [],
            }
        else:
            if hasattr(object, '__dict__'):
                encoding = 'object_dict'
                snapshot = {
                    'is_curr_element': False,
                    'name': type(object).__name__,
                    'parents': [],
                    'bindings': {
                        key: self.reference_snapshot(value, memory_state)
                        for key, value in object.__dict__.items()
                    },
                    'return_value': None,
                    'flags': [],
                }
                # TODO: Might some objects have a lot of items in their __dict__? Some ideas ...
                # (*) Make it an option [default ON] to render the contents in object frames.
                # (*) Limit the size of each object frame, but make the contents scrollable on the site.
                # (*) Include a button next to each object frame, which you can click to toggle whether to render the contents of that particular object frame.
            else:
                encoding = 'object_repr'
                snapshot = {
                    'repr': repr(object),
                }
        return {
            'encoding': encoding, # So the decoder knows the structure of `snapshot`.
            'object': snapshot,
        }

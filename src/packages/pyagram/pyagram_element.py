import inspect
import math

from . import constants
from . import enum
from . import utils

class PyagramElement:
    """
    """

    def __init__(self, opened_by, state):
        self.opened_by = opened_by
        self.state = opened_by.state if state is None else state
        self.flags = []
        self.is_new = True

    def step(self):
        """
        """
        for flag in self.flags:
            flag.step()

    def add_flag(self, banner, **init_args):
        """
        """
        flag = PyagramFlag(self, banner, **init_args)
        self.flags.append(flag)
        return flag

class PyagramFlag(PyagramElement):
    """
    """

    def __init__(self, opened_by, banner_elements, hidden_snapshot=math.inf, *, state=None):
        super().__init__(opened_by, state)
        if banner_elements is None:
            # TODO: This is totally broken now.
            # TODO: Do you even need this if clause anymore?
            banner_elements = []
        else:
            utils.concatenate_adjacent_strings(banner_elements)
        self.banner_elements = banner_elements
        self.banner_bindings = []
        self.hidden_snapshot = hidden_snapshot
        self.hidden_subflags = False
        self.frame = None

    @property
    def has_returned(self):
        """
        """
        return self.frame is not None and self.frame.has_returned

    @property
    def return_value(self):
        """
        """
        assert self.has_returned
        return self.frame.return_value

    def hide_from(self, snapshot_index):
        """
        """
        self.hidden_snapshot = min(self.hidden_snapshot, snapshot_index)

    def is_hidden(self, snapshot_index=None):
        """
        """
        if snapshot_index is None:
            snapshot_index = len(self.state.snapshots)
        return self.hidden_snapshot <= snapshot_index

    def step(self):
        """
        """
        if not self.is_hidden():
            referents = []
            for banner_element in self.banner_elements:
                if type(banner_element) is tuple:
                    _, binding_idx, unpacking_code = banner_element
                    if binding_idx < len(self.banner_bindings):
                        binding = self.banner_bindings[binding_idx]
                        unpacking_type = enum.UnpackingTypes.identify_unpacking_type(unpacking_code)
                        if unpacking_type is enum.UnpackingTypes.NORMAL:
                            referents.append(binding)
                        elif unpacking_type is enum.UnpackingTypes.SINGLY_UNPACKED:
                            for element in [*binding]:
                                referents.append(element)
                        elif unpacking_type is enum.UnpackingTypes.DOUBLY_UNPACKED:
                            for key, value in {**binding}:
                                # TODO: Should you also track the key? In case of f(**{1: 2})?
                                referents.append(value)
                        else:
                            raise enum.UnpackingTypes.illegal_enum(unpacking_type)
            for referent in referents:
                self.state.memory_state.track(referent)
        if self.frame is not None:
            self.frame.step()
        self.is_new = False # TODO: Do you still need this?
        super().step()

    def snapshot(self):
        """
        """
        # TODO: Make sure *args and **kwargs show up properly on the banner.
        # TODO: Make sure *dict and **dict behave how they respectively ought.
        # TODO: Make sure f(x=...) makes x= show up on the bottom of the banner.
        is_hidden = self.is_hidden()
        return {
            'is_curr_element': self is self.state.program_state.curr_element,
            'banner': [
                self.encode_banner_element(banner_element)
                for banner_element in self.banner_elements
            ],
            'frame':
                None
                if self.frame is None or is_hidden
                else self.frame.snapshot(),
            'flags':
                []
                if self.hidden_subflags
                else [
                    flag.snapshot()
                    for flag in self.flags + (
                        self.frame.flags
                        if is_hidden and self.frame is not None
                        else []
                    )
                ],
            'self': self, # For postprocessing.
        }

    def encode_banner_element(self, banner_element):
        """
        """
        # TODO: This should not be a function, or at least not here. Maybe move it to encode.py?
        if type(banner_element) is tuple:
            code, binding_idx, unpacking_code = banner_element
            if binding_idx < len(self.banner_bindings):
                binding = self.banner_bindings[binding_idx]
                unpacking_type = enum.UnpackingTypes.identify_unpacking_type(unpacking_code)
                if unpacking_type is enum.UnpackingTypes.NORMAL:
                    bindings = [{
                        'key': None,
                        'value': self.state.encoder.reference_snapshot(binding)
                    }]
                elif unpacking_type is enum.UnpackingTypes.SINGLY_UNPACKED:
                    bindings = [
                        {
                            'key': None,
                            'value': self.state.encoder.reference_snapshot(value)
                        }
                        for value in [*binding]
                    ]
                elif unpacking_type is enum.UnpackingTypes.DOUBLY_UNPACKED:
                    bindings = [
                        {
                            'key': key,
                            'value': self.state.encoder.reference_snapshot(value)
                        }
                        for key, value in {**binding}
                    ]
                else:
                    raise enum.UnpackingTypes.illegal_enum(unpacking_type)
            else:
                bindings = [None]
        else:
            code = banner_element
            bindings = []
        # TODO: What if you try f(**{1: 2})? Perhaps it'd be wise to use encode_mapping with is_bindings=True.
        # TODO: When you write f(1, 2, *[3, 4], a=5, **{'b': 6, 'c': 7, **{'d': 8}}, e=9), you should see `a=`, `b=`, `c=`, ..., and `e=` in all the appropriate locations on the bottom half of the banner. (And verify the top half of the banner looks good too.)
        return {
            'code': code,
            'bindings': bindings,
        }

    def fix_obj_instantiation_banner(self):
        """
        """
        pass # TODO
        # if 0 < len(self.banner_elements) and isinstance(self.banner_elements[0], tuple):
        #     _, binding_indices = self.banner_elements[0]
        #     self.banner_elements[0] = ('__init__', binding_indices)

    def add_frame(self, frame, frame_type, **init_args):
        """
        """
        # assert self.banner_is_complete
        frame = PyagramFrame(self, frame, frame_type, **init_args)
        self.frame = frame
        return frame

    def close(self):
        """
        """
        if self.frame is None:
            self.hide_from(0)
        return self.opened_by

class PyagramFrame(PyagramElement):
    """
    """

    def __init__(self, opened_by, frame, frame_type, is_implicit=False, *, state=None, function=None):
        super().__init__(opened_by, state)
        self.frame = frame
        if frame_type is None:
            self.function = utils.get_function(frame)
            self.generator = utils.get_generator(frame)
            if self.generator is None:
                frame_type = enum.PyagramFrameTypes.FUNCTION
            else:
                frame_type = enum.PyagramFrameTypes.GENERATOR
        else:
            self.function = None
            self.generator = None
        self.frame_type = frame_type
        self.is_implicit = is_implicit
        if self.is_global_frame:
            del frame.f_globals['__builtins__']
        elif self.is_builtin_frame:
            assert function is not None
            self.function = function
            self.frame_number = self.state.program_state.register_frame()
        elif self.is_function_frame:
            self.frame_number = self.state.program_state.register_frame()
            self.state.memory_state.record_function(self, self.function)
            var_positional_index, var_positional_name, var_keyword_name = utils.get_variable_params(self.function)
            self.var_positional_index = var_positional_index
            self.initial_var_pos_args = None if var_positional_name is None else [
                self.state.encoder.reference_snapshot(positional_argument)
                for positional_argument in frame.f_locals[var_positional_name]
            ]
            self.initial_var_keyword_args = None if var_keyword_name is None else {
                key: self.state.encoder.reference_snapshot(value)
                for key, value in frame.f_locals[var_keyword_name].items()
            }
            self.initial_bindings = {
                key: self.state.encoder.reference_snapshot(value)
                for key, value in self.get_bindings().items()
            }
            if is_implicit:
                # TODO: This is broken now.
                flag = opened_by
                num_args = len(self.initial_bindings)
                num_bindings = 1 + num_args
                flag.banner_elements = [
                    (
                        self.function.__name__,
                        [0],
                    ),
                    '(',
                    (
                        '...',
                        list(range(1, num_bindings)),
                    ),
                    ')',
                ]
                flag.banner_bindings = [(False, None)] * num_bindings
                flag.evaluate_next_banner_bindings(skip_args=True)
        elif self.is_generator_frame:
            self.state.memory_state.record_generator(self, self.generator)
            self.hide_from(0)
            self.throws_exc = False
        elif self.is_placeholder_frame:
            pass
        else:
            raise enum.PyagramFrameTypes.illegal_enum(self.frame_type)
        self.has_returned = False
        self.return_value = None

    def __repr__(self):
        """
        """
        if self.is_global_frame:
            return 'Global Frame'
        elif self.is_builtin_frame:
            return f'Frame {self.frame_number}'
        elif self.is_function_frame:
            return f'Frame {self.frame_number}'
        elif self.is_generator_frame:
            return f'Frame {self.state.memory_state.generator_numbers[self.generator]}'
        elif self.is_placeholder_frame:
            return '...'
        else:
            raise enum.PyagramFrameTypes.illegal_enum(self.frame_type)

    @property
    def is_global_frame(self):
        """
        """
        return self.frame_type is enum.PyagramFrameTypes.GLOBAL

    @property
    def is_builtin_frame(self):
        """
        """
        return self.frame_type is enum.PyagramFrameTypes.BUILTIN

    @property
    def is_function_frame(self):
        """
        """
        return self.frame_type is enum.PyagramFrameTypes.FUNCTION

    @property
    def is_generator_frame(self):
        """
        """
        return self.frame_type is enum.PyagramFrameTypes.GENERATOR

    @property
    def is_placeholder_frame(self):
        """
        """
        return self.frame_type is enum.PyagramFrameTypes.PLACEHOLDER

    @property
    def parent(self):
        """
        """
        if self.is_global_frame:
            return None
        elif self.is_builtin_frame:
            return self.state.program_state.global_frame
        elif self.is_function_frame:
            return self.state.memory_state.function_parents[self.function]
        elif self.is_generator_frame:
            return self.state.memory_state.generator_parents[self.generator]
        elif self.is_placeholder_frame:
            return None
        else:
            raise enum.PyagramFrameTypes.illegal_enum(self.frame_type)

    @property
    def shows_bindings(self):
        """
        """
        return self.is_global_frame \
            or self.is_function_frame \
            or self.is_generator_frame

    @property
    def shows_return_value(self):
        """
        """
        if self.is_global_frame:
            return False
        elif self.is_builtin_frame:
            return self.has_returned
        elif self.is_function_frame:
            return self.has_returned
        elif self.is_generator_frame:
            return self.has_returned and not self.throws_exc
        elif self.is_placeholder_frame:
            return False
        else:
            raise enum.PyagramFrameTypes.illegal_enum(self.frame_type)

    def hide_from(self, snapshot_index):
        """
        """
        if self.opened_by is not None:
            self.opened_by.hide_from(snapshot_index)

    def is_hidden(self, snapshot_index=None):
        """
        """
        return self.opened_by is not None and self.opened_by.is_hidden(snapshot_index)

    def step(self):
        """
        """
        if self.shows_bindings:
            self.bindings = self.get_bindings()
            if not self.is_hidden():
                referents = list(self.bindings.values())
                if self.function is not None:
                    referents.append(self.function)
                if self.generator is not None:
                    referents.append(self.generator)
                if self.shows_return_value:
                    referents.append(self.return_value)
                for referent in referents:
                    self.state.memory_state.track(referent)
        super().step()

    def snapshot(self):
        """
        """
        return {
            'type': 'function',
            'is_curr_element': self is self.state.program_state.curr_element,
            'name': repr(self),
            'parent':
                None
                if self.parent is None
                else repr(self.parent),
            'bindings': self.state.encoder.encode_mapping(
                self.bindings if self.shows_bindings else {},
                is_bindings=True,
            ),
            'return_value':
                self.state.encoder.reference_snapshot(self.return_value)
                if self.shows_return_value
                else None,
            'from': None,
            'flags': [
                flag.snapshot()
                for flag in self.flags
            ],
        }

    def get_bindings(self):
        """
        """
        sorted_binding_names = [] if self.function is None else list(
            inspect.signature(self.function).parameters.keys(),
        )
        for variable, value in self.frame.f_locals.items():
            is_in_parent_frame = False
            next_frame_to_scan = self.parent
            while next_frame_to_scan is not None:
                if variable in next_frame_to_scan.frame.f_locals and next_frame_to_scan.frame.f_locals[variable] == value:
                    is_in_parent_frame = True
                    break
                next_frame_to_scan = next_frame_to_scan.parent
            if variable in self.frame.f_code.co_varnames or not is_in_parent_frame:
                sorted_binding_names.append(variable)
        return {
            variable: self.frame.f_locals[variable]
            for variable in sorted_binding_names
        }

    def close(self, return_value, *, is_gen_exc=False):
        """
        """
        if not self.is_global_frame:
            if self.is_generator_frame:
                self.throws_exc = is_gen_exc
            self.has_returned = True
            self.return_value = return_value
        self.state.step()
        return self.opened_by

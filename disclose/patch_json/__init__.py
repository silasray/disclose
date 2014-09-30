from disclose import OperandMetadata
import json.encoder, sys
 
original_encode = json.encoder.JSONEncoder.encode
original_iterencode = json.encoder.JSONEncoder.iterencode
 
def encode(self, o):
     
    try:
        o = OperandMetadata.for_(o).operand
    except:
        pass
    return original_encode(self, o)
 
def iterencode(self, o, _one_shot):
     
    try:
        o = OperandMetadata.for_(o).operand
    except:
        pass
    return original_iterencode(self, o, _one_shot)
 
json.encoder.JSONEncoder.encode = encode
json.encoder.JSONEncoder.iterencode = iterencode


class ObjectWrapperAwareJSONEncoder(json.encoder.JSONEncoder):
    
    def default(self, o):
        
        try:
            return OperandMetadata.for_(o).operand
        except:
            super(ObjectWrapperAwareJSONEncoder, self).default(o)


if sys.version_info.major == 2:
    from disclose.patch_json.py2 import _make_iterencode
elif sys.version_info.major == 3:
    from disclose.patch_json.py3 import _make_iterencode

json.encoder._make_iterencode = _make_iterencode
# Have to set this to None to supersede use of builtin c encoder
# probably slows things down, but no other way to get the encoder to work
json.encoder.c_make_encoder = None
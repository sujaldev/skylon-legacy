# JULY 1
Found ambiguity in the specification for the NAMED CHARACTER REFERENCE STATE as to
how to "Consume the maximum number of characters possible" a mozilla contributor stated
that this was "arguably a bug". He explained the algorithm to "Consume the maximum number 
of characters possible" as a procedure to find the longest valid Named character reference.
If the longest reference is invalid, switch back to the last successful match if it exists,
and if not, set the validity to false.

Example:

>Both `&cent` and `&cent;` are valid so if the algorithm gets &center; as input it will output
`¢`er; as output since `&center;` is invalid, and the last successful match is `&cent.`
> 
>`&centerdot;` is valid and will produce `·`
---
# JULY 2
> There seems to be some ambiguity in the process of reconsumption in the html specs
and the code.

---
# JULY 3
I discovered the token structure described in the html specification and will now 
be implementing it. There are only a few types of tokens:

### DOCTYPE
```python
token = {
    "token-type": "DOCTYPE",
    
    "name": "missing",  # missing is not the same as an empty string ""
    "public-identifier": "missing",
    "system-identifier": "missing",
    "force-quirks": False  # Off and On
}
```

### START TAG
```python
token = {
    "token-type": "start-tag",
    
    "tag-name": "",
    "self-closing-flag": "unset",  # other state is set
    "attributes": [
        ["attribute-name", "attribute-value"],
        ["attribute-name", "attribute-value"],
    ]
}
```

### END TAG
```python
token = {
    "token-type": "end-tag",
    
    "tag-name": "",
    "self-closing-flag": "unset",  # other state is set
    "attributes": [
        ["attribute-name", "attribute-value"],
        ["attribute-name", "attribute-value"],
    ]
}
```

### COMMENT
```python
token = {
    "token-type": "comment",
    
    "data": ""
}
```

### CHARACTER
```python
token = {
    "token-type": "character",
    
    "data": ""
}
```

### EOF (END OF FILE)
```python
token = {
    "token-type": "eof",
}
```

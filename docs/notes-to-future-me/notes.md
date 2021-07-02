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

# JULY 2
> There seems to be some ambiguity in the process of reconsumption in the html specs
and the code.
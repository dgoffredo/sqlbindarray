![sqlbindarray](sqlbindarray.png)

sqlbindarray
============
Replace named parameters with python values in SQL statements, including lists.

Why
---
Ever wanted to do this?
```sql
select Foo, Bar from Thing where Trait in @bound_parameter;
```
Well, you can't, can you? It's ok, because now you can.

What
----
`sqlbindarray` is a python package providing a function, `replace`, that allows
specified named parameters in a SQL statement to be replaced by SQL literal
values derived from python values, e.g.
```python
import sqlbindarray

print(sqlbindarray.replace("select * from T where x = @x and y in @y;", {
                               'y': (1, 2, "three")
}))
```
prints
```sql
select * from T where x = @x and y in (1, 2, 'three');
```

How
---
The [sqlbindarray/](sqlbindarray/) subdirectory of this repository can be
dropped into a python project and imported as if it were a local module.

More
----
### Supported Named Parameter Syntaxes
`sqlbindarray` recognizes any of the following syntaxes for named parameters:
- `@parameter_name`
- `:parameter_name`
- `%(parameter_name)s`
- `@"parameter name"`
- `:"parameter name"`

### Array Parameter Length Syntax Extension
`sqlbindarray` supports an extension to the SQL language. Any named parameter
can be preceded by the `#` character. If preceded by the `#` character, then
the combined expression (the hash character and the named parameter) will be
replaced by the length of the bound value rather than by its value. This could
be useful in this kind of situation:

    select * from Tickets where #@teams = 0 or Team in @teams;

### Limitations
`sqlbindarray` doesn't support date, time, or datetime python values. This
sucks, but getting them to work portably is not easy. Database systems have
multiple datetime-related storage types that map differently to python datetime
types. Datetime support may be added in the future.
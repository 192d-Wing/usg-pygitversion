""".NET compatibility shims.

GitVersion's configuration surface leaks two .NET-isms that users rely on:
the .NET regular-expression dialect (named groups as ``(?<name>...)``) and
.NET custom date-format strings (``yyyy-MM-dd``). These modules translate
both so that existing ``GitVersion.yml`` files work unchanged.
"""

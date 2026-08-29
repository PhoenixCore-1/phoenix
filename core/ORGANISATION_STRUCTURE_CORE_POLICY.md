# Phoenix Core Organisation Structure v1.0

Phoenix Core provides a generic company structure:

Organisation
  -> Branch / Location
       -> one or more Warehouses

## Organisation

The organisation is the top-level business tenant/company in Phoenix.

## Branch / Location

A branch is an operating/business location. Phoenix does not assume any
specific customer branch names.

## Warehouse

A warehouse is a storage/stock location associated with a branch. A branch
may have zero, one or multiple warehouses.

Branch and warehouse are intentionally separate concepts.

## User access

Users remain Core identities. User records can be associated with an
organisation and branch. Future module-specific access rules may use the
warehouse relationship, but Core does not embed customer-specific warehouse
logic.

## Commercial rule

No Upat-specific branches, warehouses or operational assumptions belong in
Phoenix Core.

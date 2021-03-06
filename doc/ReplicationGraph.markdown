# Replication Graph

The replication graph contains the mysql replication information for a shard. Currently, we only support one layer
of replication (a single master wiht multiple slaves), but the design doesn't preclude us from supporting
hierarchical replication later on.

## Master

The current master for a shard is represented in the Shard object as MasterAlias, in the global topology server.

When creating a master (using 'vtctl InitTablet ... master'), we make sure MasterAlias is empty in the Shard record, and refuse to proceed if not (unless -force-master is specified). After creation, we update MasterAlias in the Shard.

## Slaves

The slaves are added to the ShardReplication object present on each local topology server. So for slaves, the
replication graph is colocated in the same cell as the tablets themselves. This makes disaster recovery much easier:
when loosing a data center, the replication graph for other data centers is not lost.

When creating a slave (using 'vtctl InitTablet ... replica' for instance), we get the master record (if not specified) from the MasterAlias of the Shard. We then add an entry in the ReplicationLinks list of the ShardReplication object for the tablet’s cell (we create ShardReplication if it doesn’t exist yet).

## Discovery

When looking for all the tablets in a Shard, we look for the Shard record, start the list with the MasterAlias, and read the 'Cells' list. Then for each Cell, we get the ShardReplication object, and find all the tablets, and add them to the list.

If a cell is down, the result is partial. Some actions are resilient to partial results, like reparenting.

## Reparenting

[Reparenting](Reparenting.markdown) will update the MasterAlias record in the Shard (after having acquired the Shard lock). See the Reparenting doc for more information.

"""Friendship representation notes.

Edges are stored twice (A→B and B→A) so listing friends is an indexed
query on user_id. Production shards by user_id keep each user's outbound
edges on that user's shard.
"""

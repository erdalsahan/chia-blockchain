import asyncio
from pathlib import Path
from secrets import token_bytes
import aiosqlite
import pytest

from chia.protocols import full_node_protocol
from chia.types.full_block import FullBlock
from chia.types.header_block import HeaderBlock
from chia.types.weight_proof import WeightProof
from chia.util.db_wrapper import DBWrapper
from chia.util.generator_tools import get_block_header
from chia.wallet.key_val_store import KeyValStore
from chia.wallet.wallet_blockchain import WalletBlockchain
from tests.setup_nodes import bt, test_constants, setup_node_and_wallet


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


class TestWalletBlockchain:
    @pytest.fixture(scope="function")
    async def wallet_node(self):
        async for _ in setup_node_and_wallet(test_constants):
            yield _

    @pytest.mark.asyncio
    async def test_wallet_blockchain(self, wallet_node, default_1000_blocks):
        full_node_api, wallet_node, full_node_server, wallet_server = wallet_node

        for block in default_1000_blocks[:600]:
            await full_node_api.full_node.respond_block(full_node_protocol.RespondBlock(block))

        res = await full_node_api.request_proof_of_weight(
            full_node_protocol.RequestProofOfWeight(
                default_1000_blocks[499].height + 1, default_1000_blocks[499].header_hash
            )
        )
        res_2 = await full_node_api.request_proof_of_weight(
            full_node_protocol.RequestProofOfWeight(
                default_1000_blocks[460].height + 1, default_1000_blocks[460].header_hash
            )
        )

        res_3 = await full_node_api.request_proof_of_weight(
            full_node_protocol.RequestProofOfWeight(
                default_1000_blocks[505].height + 1, default_1000_blocks[505].header_hash
            )
        )
        weight_proof: WeightProof = full_node_protocol.RespondProofOfWeight.from_bytes(res.data).wp
        weight_proof_short: WeightProof = full_node_protocol.RespondProofOfWeight.from_bytes(res_2.data).wp
        weight_proof_long: WeightProof = full_node_protocol.RespondProofOfWeight.from_bytes(res_3.data).wp

        wallet = wallet_node.wallet_state_manager.main_wallet

        db_filename = Path("wallet_store_test.db")

        if db_filename.exists():
            db_filename.unlink()

        db_connection = await aiosqlite.connect(db_filename)
        db_wrapper = DBWrapper(db_connection)
        store = await KeyValStore.create(db_wrapper)
        chain = await WalletBlockchain.create(store, constants=test_constants)
        try:
            assert (await chain.get_peak_block()) is None
            assert chain.get_peak_height() == 0
            assert chain.get_latest_timestamp() == 0

            await chain.new_weight_proof(weight_proof, wallet_node.wallet_state_manager.weight_proof_handler)
            assert (await chain.get_peak_block()) is not None
            assert chain.get_peak_height() == 499
            assert chain.get_latest_timestamp() > 0

            await chain.new_weight_proof(weight_proof_short, wallet_node.wallet_state_manager.weight_proof_handler)
            assert chain.get_peak_height() == 499

            await chain.new_weight_proof(weight_proof_long, wallet_node.wallet_state_manager.weight_proof_handler)
            assert chain.get_peak_height() == 505

            header_blocks = []
            for block in default_1000_blocks:
                header_block = get_block_header(block, [], [])
                header_blocks.append(header_block)
            assert await chain.validate_blocks(header_blocks[506:])

            assert await chain.validate_blocks(header_blocks[105:])

            assert not (await chain.validate_blocks(header_blocks[507:]))

            assert chain.get_peak_height() == 505
            await chain.new_blocks(header_blocks[506])

            assert chain.get_peak_height() == 506

        finally:
            await db_connection.close()
            db_filename.unlink()

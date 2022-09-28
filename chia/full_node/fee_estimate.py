from dataclasses import dataclass
from typing import List, Optional

from chia.types.fee_rate import FeeRate
from chia.util.ints import uint64
from chia.util.streamable import Streamable, streamable


@streamable
@dataclass(frozen=True)
class FeeEstimate(Streamable):
    """
    time_target: Epoch time in seconds we are targeting to include our `SpendBundle` in the blockchain.
    estimated_fee: expressed in mojo per 1 clvm_cost. `estimated_fee` can be zero.
    """

    error: Optional[str]
    time_target: uint64  # TODO: relative vs. absolute unix time stamp in seconds
    # estimated_fee: uint64  # Mojos per clvm cost
    estimated_fee_rate: FeeRate


@streamable
@dataclass(frozen=True)
class FeeEstimates(Streamable):
    """
    Estimates here will be x mojo / 1 clvm_cost.
    """

    error: Optional[str]
    estimates: List[FeeEstimate]

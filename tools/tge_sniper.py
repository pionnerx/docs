"""Utility to batch snipe TGE using multiple wallets.

This script derives multiple wallets from a given mnemonic and sends approve
and purchase transactions using raw bytecode. Transactions are retried with an
escalating gas price when they fail.

Dependencies: web3, eth-account
"""

import argparse
import asyncio
import os
from typing import List

from eth_account import Account
from web3 import AsyncWeb3, HTTPProvider

# Derive 50 wallets from mnemonic
def derive_accounts(mnemonic: str, count: int = 50) -> List[Account]:
    accounts = []
    for i in range(count):
        acct = Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}")
        accounts.append(acct)
    return accounts

# Replace a parameter in raw tx data at the given index with new value (uint256)

def replace_param(data_hex: str, index: int, new_value: int) -> str:
    data = data_hex[2:] if data_hex.startswith("0x") else data_hex
    if len(data) < 8 + 64 * (index + 1):
        raise ValueError("Data too short for provided index")
    prefix = data[:8]
    params = [data[8 + 64 * i : 8 + 64 * (i + 1)] for i in range((len(data) - 8) // 64)]
    params[index] = f"{new_value:064x}"
    return "0x" + prefix + "".join(params)

# Build approve calldata for spender and token contract

def build_approve_data(spender: str) -> str:
    function_selector = "095ea7b3"  # approve(address,uint256)
    padded_spender = spender.lower().replace("0x", "").rjust(64, "0")
    max_uint = "f" * 64
    return "0x" + function_selector + padded_spender + max_uint

async def send_with_retry(w3: AsyncWeb3, account: Account, tx: dict, gas_price_gwei: int, retries: int = 3) -> str:
    for attempt in range(retries):
        tx["gasPrice"] = w3.to_wei(gas_price_gwei, "gwei")
        tx["nonce"] = await w3.eth.get_transaction_count(account.address)
        signed = account.sign_transaction(tx)
        try:
            tx_hash = await w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                return tx_hash.hex()
        except Exception:
            gas_price_gwei = int(gas_price_gwei * 1.2)
    raise RuntimeError("transaction failed after retries")

async def main():
    parser = argparse.ArgumentParser(description="Batch TGE sniping tool")
    parser.add_argument("--mnemonic", required=True, help="wallet mnemonic")
    parser.add_argument("--spender", required=True, help="TGE contract address")
    parser.add_argument("--token", required=True, help="BEP20 token address")
    parser.add_argument("--raw", required=True, help="purchase calldata")
    parser.add_argument("--gas", type=int, default=5, help="initial gas price in gwei")
    parser.add_argument("--min-index", type=int, default=None, help="position of minAmountOut parameter")
    args = parser.parse_args()

    w3 = AsyncWeb3(HTTPProvider(os.environ.get("BSC_NODE", "https://bsc-dataseed.binance.org")))
    accounts = derive_accounts(args.mnemonic)

    purchase_data = args.raw
    if args.min_index is not None:
        purchase_data = replace_param(purchase_data, args.min_index, 0)

    approve_data = build_approve_data(args.spender)

    async def handle_account(acct: Account):
        approve_tx = {
            "to": args.token,
            "value": 0,
            "gas": 100000,
            "data": approve_data,
        }
        buy_tx = {
            "to": args.spender,
            "value": 0,
            "gas": 500000,
            "data": purchase_data,
        }
        await send_with_retry(w3, acct, approve_tx, args.gas)
        await send_with_retry(w3, acct, buy_tx, args.gas)

    await asyncio.gather(*(handle_account(a) for a in accounts))

if __name__ == "__main__":
    asyncio.run(main())

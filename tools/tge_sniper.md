# TGE Sniper Script

`tge_sniper.py` automates sending approve and purchase transactions across the
first 50 wallets derived from a mnemonic.

```
python tools/tge_sniper.py --mnemonic "word word ..." \
  --spender 0xTGEAddress --token 0xTokenAddress \
  --raw 0xYourPurchaseCalldata --gas 5 --min-index 1
```

- `--min-index` selects which parameter in the raw calldata to replace with `0`
  in case it encodes `minAmountOut`.
- `--gas` sets the starting gas price in gwei. Failed transactions retry with a
  higher price.

Ensure `web3` and `eth-account` are installed:
`pip install web3 eth-account`.

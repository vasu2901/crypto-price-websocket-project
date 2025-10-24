import React, { useEffect, useState, useRef } from "react";

const WEBSOCKET_URL = "wss://crypto-price-websocket-project.onrender.com/ws"; // your backend URL

export default function CryptoPrices() {
    const [prices, setPrices] = useState({});
    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);

    useEffect(() => {
        function connect() {
            const ws = new WebSocket(WEBSOCKET_URL);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log("Connected to WebSocket server");
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === "snapshot") {
                        setPrices(data.prices);
                    } else if (data.symbol) {
                        setPrices((prev) => ({
                            ...prev,
                            [data.symbol]: data,
                        }));
                    }
                } catch (err) {
                    console.error("Error parsing WebSocket message:", err);
                }
            };

            ws.onclose = () => {
                console.warn("WebSocket disconnected. Retrying in 5 seconds...");
                reconnectTimer.current = setTimeout(connect, 5000);
            };

            ws.onerror = (err) => {
                console.error("WebSocket error:", err);
                ws.close();
            };
        }

        connect();

        // cleanup
        return () => {
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            if (wsRef.current) wsRef.current.close();
        };
    }, []);

    const symbols = Object.keys(prices);

    return (
        <div style={styles.container}>
            <h1 style={styles.header}>Live Crypto Prices</h1>
            {symbols.length === 0 ? (
                <p>Connecting to live prices...</p>
            ) : (
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Price (USDT)</th>
                            <th>Change (%)</th>
                            <th>Last Updated (UTC)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {symbols.map((symbol) => {
                            const p = prices[symbol];
                            const color = p.priceChangePercent > 0 ? "limegreen" : "red";
                            return (
                                <tr key={symbol}>
                                    <td>{symbol}</td>
                                    <td>{p.lastPrice.toFixed(2)}</td>
                                    <td style={{ color }}>
                                        {p.priceChangePercent?.toFixed(2)}%
                                    </td>
                                    <td>{p.eventTime}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            )}
        </div>
    );
}

const styles = {
    container: {
        padding: "2rem",
        fontFamily: "Arial, sans-serif",
        backgroundColor: "#111",
        color: "#fff",
        minHeight: "100vh",
    },
    header: {
        textAlign: "center",
    },
    table: {
        margin: "2rem auto",
        borderCollapse: "collapse",
        width: "80%",
        backgroundColor: "#222",
    },
};

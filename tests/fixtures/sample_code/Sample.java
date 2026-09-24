package com.example.service;

import java.util.List;
import java.util.ArrayList;

/**
 * Sample Java service class for testing.
 */
public class OrderService {
    private final List<String> orders;

    public OrderService() {
        this.orders = new ArrayList<>();
    }

    public void addOrder(String orderId) {
        if (orderId != null && !orderId.isEmpty()) {
            this.orders.add(orderId);
        }
    }

    public int getOrderCount() {
        return this.orders.size();
    }
}

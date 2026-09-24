/**
 * Sample TypeScript file for testing.
 */
import { User, Config } from "./types";
import * as path from "path";

export interface UserProfile {
    id: string;
    username: string;
    isActive: boolean;
}

export class UserService {
    private config: Config;

    constructor(config: Config) {
        this.config = config;
    }

    public async getUserById(userId: string): Promise<UserProfile | null> {
        if (!userId) {
            return null;
        }
        return {
            id: userId,
            username: "testuser",
            isActive: true,
        };
    }
}

export function formatGreeting(name: string): string {
    return `Hello, ${name}!`;
}

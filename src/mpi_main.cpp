/**
 * @file mpi_main.cpp
 * @brief MPI-distributed implementation of Langton's Ant simulator with domain decomposition.
 *
 * Implements 1D row-wise domain partitioning with ghost row updates via MPI_Sendrecv,
 * dynamic agent migration between processes, and periodic snapshot gathering.
 * Supports multiple ants with collision resolution via priority ordering.
 *
 * @author Cocriș Iulian
 * @date June 2026
 * @version 1.0
 */

#include <mpi.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace std;

/**
 * @struct Ant
 * @brief Agent representation (same as sequential version).
 * @see main.cpp
 */
struct Ant {
    int id;  ///< Unique agent identifier
    int x;   ///< X coordinate
    int y;   ///< Y coordinate
    int dir; ///< Direction: 0=North, 1=East, 2=South, 3=West
    int steps_matching;
    int history_dir[104];
    int history_dx[104];
    int history_dy[104];
};

const int ANT_PACK_SIZE = 5 + 3 * 104;

struct Intent {
    int id;
    int src_x;
    int src_y;
    int dst_x;
    int dst_y;
    int new_dir;
    int dst_rank;
};

static int wrap_coord(int value, int limit) {
    value %= limit;
    if (value < 0) {
        value += limit;
    }
    return value;
}

static void build_partition(int n, int world_size, vector<int> &row_start, vector<int> &row_count) {
    row_start.resize(world_size);
    row_count.resize(world_size);

    int base = n / world_size;
    int remainder = n % world_size;
    int offset = 0;
    for (int rank = 0; rank < world_size; ++rank) {
        row_start[rank] = offset;
        row_count[rank] = base + (rank < remainder ? 1 : 0);
        offset += row_count[rank];
    }
}

static int owner_of_row(int row, const vector<int> &row_start, const vector<int> &row_count) {
    for (size_t rank = 0; rank < row_start.size(); ++rank) {
        if (row >= row_start[rank] && row < row_start[rank] + row_count[rank]) {
            return static_cast<int>(rank);
        }
    }
    return static_cast<int>(row_start.size() - 1);
}

static void write_ppm(const string &filename, const vector<uint8_t> &grid, int n, const vector<Ant> &ants) {
    vector<unsigned char> img(3 * n * n);
    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            int i = (y * n + x) * 3;
            if (grid[y * n + x] == 0) {
                img[i + 0] = 255;
                img[i + 1] = 255;
                img[i + 2] = 255;
            } else {
                img[i + 0] = 0;
                img[i + 1] = 0;
                img[i + 2] = 0;
            }
        }
    }

    for (const auto &ant : ants) {
        int x = wrap_coord(ant.x, n);
        int y = wrap_coord(ant.y, n);
        int i = (y * n + x) * 3;
        img[i + 0] = 255;
        img[i + 1] = 0;
        img[i + 2] = 0;
    }

    ofstream ofs(filename, ios::binary);
    ofs << "P6\n" << n << " " << n << "\n255\n";
    ofs.write(reinterpret_cast<char *>(img.data()), static_cast<streamsize>(img.size()));
}

static vector<int> pack_intents(const vector<Intent> &intents) {
    vector<int> packed;
    packed.reserve(intents.size() * 7);
    for (const auto &intent : intents) {
        packed.push_back(intent.id);
        packed.push_back(intent.src_x);
        packed.push_back(intent.src_y);
        packed.push_back(intent.dst_x);
        packed.push_back(intent.dst_y);
        packed.push_back(intent.new_dir);
        packed.push_back(intent.dst_rank);
    }
    return packed;
}

static vector<Intent> unpack_intents(const vector<int> &packed) {
    vector<Intent> intents;
    intents.reserve(packed.size() / 7);
    for (size_t i = 0; i + 6 < packed.size(); i += 7) {
        Intent intent{};
        intent.id = packed[i + 0];
        intent.src_x = packed[i + 1];
        intent.src_y = packed[i + 2];
        intent.dst_x = packed[i + 3];
        intent.dst_y = packed[i + 4];
        intent.new_dir = packed[i + 5];
        intent.dst_rank = packed[i + 6];
        intents.push_back(intent);
    }
    return intents;
}

static vector<int> pack_ants(const vector<Ant> &ants) {
    vector<int> packed;
    packed.reserve(ants.size() * ANT_PACK_SIZE);
    for (const auto &ant : ants) {
        packed.push_back(ant.id);
        packed.push_back(ant.x);
        packed.push_back(ant.y);
        packed.push_back(ant.dir);
        packed.push_back(ant.steps_matching);
        for (int j = 0; j < 104; ++j) packed.push_back(ant.history_dir[j]);
        for (int j = 0; j < 104; ++j) packed.push_back(ant.history_dx[j]);
        for (int j = 0; j < 104; ++j) packed.push_back(ant.history_dy[j]);
    }
    return packed;
}

static vector<Ant> unpack_ants(const vector<int> &packed) {
    vector<Ant> ants;
    ants.reserve(packed.size() / ANT_PACK_SIZE);
    for (size_t i = 0; i + (ANT_PACK_SIZE - 1) < packed.size(); i += ANT_PACK_SIZE) {
        Ant ant{};
        ant.id = packed[i + 0];
        ant.x = packed[i + 1];
        ant.y = packed[i + 2];
        ant.dir = packed[i + 3];
        ant.steps_matching = packed[i + 4];
        for (int j = 0; j < 104; ++j) ant.history_dir[j] = packed[i + 5 + j];
        for (int j = 0; j < 104; ++j) ant.history_dx[j] = packed[i + 5 + 104 + j];
        for (int j = 0; j < 104; ++j) ant.history_dy[j] = packed[i + 5 + 208 + j];
        ants.push_back(ant);
    }
    return ants;
}

static void exchange_ghost_rows(vector<uint8_t> &grid, int n, int local_rows, int rank, int world_size) {
    if (world_size == 1) {
        if (local_rows > 0) {
            copy(grid.begin() + n * local_rows, grid.begin() + n * (local_rows + 1), grid.begin());
            copy(grid.begin() + n, grid.begin() + 2 * n, grid.begin() + n * (local_rows + 1));
        }
        return;
    }

    int north = (rank - 1 + world_size) % world_size;
    int south = (rank + 1) % world_size;

    MPI_Sendrecv(&grid[n], n, MPI_UNSIGNED_CHAR, north, 0,
                 &grid[(local_rows + 1) * n], n, MPI_UNSIGNED_CHAR, south, 0,
                 MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    MPI_Sendrecv(&grid[local_rows * n], n, MPI_UNSIGNED_CHAR, south, 1,
                 &grid[0], n, MPI_UNSIGNED_CHAR, north, 1,
                 MPI_COMM_WORLD, MPI_STATUS_IGNORE);
}

static void gather_and_write_snapshot(const string &filename,
                                     const vector<uint8_t> &grid,
                                     const vector<Ant> &ants,
                                     int n,
                                     int local_rows,
                                     int rank,
                                     int world_size,
                                     const vector<int> &row_count) {
    vector<int> row_counts_bytes;
    vector<int> row_displs_bytes;
    vector<uint8_t> full_grid;

    if (rank == 0) {
        row_counts_bytes.resize(world_size);
        row_displs_bytes.resize(world_size);
        int offset = 0;
        for (int r = 0; r < world_size; ++r) {
            row_counts_bytes[r] = row_count[r] * n;
            row_displs_bytes[r] = offset;
            offset += row_counts_bytes[r];
        }
        full_grid.resize(n * n);
    }

    const uint8_t *send_grid = local_rows > 0 ? &grid[n] : nullptr;
    MPI_Gatherv(send_grid, local_rows * n, MPI_UNSIGNED_CHAR,
                rank == 0 ? full_grid.data() : nullptr,
                rank == 0 ? row_counts_bytes.data() : nullptr,
                rank == 0 ? row_displs_bytes.data() : nullptr,
                MPI_UNSIGNED_CHAR, 0, MPI_COMM_WORLD);

    int local_ant_count = static_cast<int>(ants.size());
    vector<int> ant_counts;
    vector<int> ant_displs;
    if (rank == 0) {
        ant_counts.resize(world_size);
    }
    MPI_Gather(&local_ant_count, 1, MPI_INT,
               rank == 0 ? ant_counts.data() : nullptr, 1, MPI_INT,
               0, MPI_COMM_WORLD);

    vector<int> packed_ants = pack_ants(ants);
    vector<int> gathered_ants;
    if (rank == 0) {
        ant_displs.resize(world_size);
        int offset = 0;
        for (int r = 0; r < world_size; ++r) {
            ant_displs[r] = offset;
            ant_counts[r] *= ANT_PACK_SIZE;
            offset += ant_counts[r];
        }
        gathered_ants.resize(offset);
    }

    MPI_Gatherv(packed_ants.empty() ? nullptr : packed_ants.data(), static_cast<int>(packed_ants.size()), MPI_INT,
                rank == 0 ? gathered_ants.data() : nullptr,
                rank == 0 ? ant_counts.data() : nullptr,
                rank == 0 ? ant_displs.data() : nullptr,
                MPI_INT, 0, MPI_COMM_WORLD);

    if (rank == 0) {
        vector<Ant> all_ants = unpack_ants(gathered_ants);
        write_ppm(filename, full_grid, n, all_ants);
    }
}

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);

    int rank = 0;
    int world_size = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &world_size);

    int n = 200;
    long long steps = 10000;
    int ants_n = 1;
    int snapshot_k = 0;
    bool wrap = true;
    bool gui_mode = false;

    for (int i = 1; i < argc; ++i) {
        string s = argv[i];
        if ((s == "-n" || s == "--size") && i + 1 < argc) {
            n = stoi(argv[++i]);
        } else if ((s == "-t" || s == "--steps") && i + 1 < argc) {
            steps = atoll(argv[++i]);
        } else if ((s == "-a" || s == "--ants") && i + 1 < argc) {
            ants_n = stoi(argv[++i]);
        } else if ((s == "-k" || s == "--snapshot") && i + 1 < argc) {
            snapshot_k = stoi(argv[++i]);
        } else if (s == "--no-wrap") {
            wrap = false;
        } else if (s == "-g" || s == "--gui") {
            gui_mode = true;
        } else if (s == "-h" || s == "--help") {
            if (rank == 0) {
                cout << "Usage: " << argv[0] << " [-n size] [-t steps] [-a ants] [-k snapshot_freq] [--no-wrap] [-g|--gui]\n";
            }
            MPI_Finalize();
            return 0;
        }
    }

    vector<int> row_start;
    vector<int> row_count;
    build_partition(n, world_size, row_start, row_count);
    int local_rows = row_count[rank];

    vector<uint8_t> grid((local_rows + 2) * n, 0);
    vector<Ant> ants;
    int cx = n / 2;
    int cy = n / 2;
    for (int i = 0; i < ants_n; ++i) {
        Ant ant{};
        ant.id = i;
        ant.x = wrap_coord(cx + (i % 3) - 1, n);
        ant.y = wrap_coord(cy + (i / 3) - 1, n);
        ant.dir = 0;
        ant.steps_matching = 0;
        for (int j = 0; j < 104; ++j) {
            ant.history_dir[j] = -1;
            ant.history_dx[j] = 99;
            ant.history_dy[j] = 99;
        }
        if (owner_of_row(ant.y, row_start, row_count) == rank) {
            ants.push_back(ant);
        }
    }

    vector<uint8_t> gui_grid;
    vector<Ant> gui_ants;
    if (gui_mode && rank == 0) {
        gui_grid.assign(n * n, 0);
        gui_ants.resize(ants_n);
        cout << "INIT " << n << " " << ants_n << " " << world_size << endl;
        for (int i = 0; i < ants_n; ++i) {
            int ax = wrap_coord(cx + (i % 3) - 1, n);
            int ay = wrap_coord(cy + (i / 3) - 1, n);
            gui_ants[i].id = i;
            gui_ants[i].x = ax;
            gui_ants[i].y = ay;
            gui_ants[i].dir = 0;
            cout << "ANT " << i << " " << ax << " " << ay << " 0" << endl;
        }
        cout << "START" << endl;
        cout.flush();
    }

    for (long long step = 1; step <= steps; ++step) {
        exchange_ghost_rows(grid, n, local_rows, rank, world_size);
        bool local_highway_detected = false;

        if (gui_mode && rank == 0) {
            cout << "STEP " << step << endl;
        }

        vector<Intent> intents;
        intents.reserve(ants.size());
        for (const auto &ant : ants) {
            int local_y = ant.y - row_start[rank] + 1;
            int local_x = ant.x;
            uint8_t color = grid[local_y * n + local_x];

            Intent intent{};
            intent.id = ant.id;
            intent.src_x = ant.x;
            intent.src_y = ant.y;
            intent.new_dir = (color == 0) ? (ant.dir + 1) % 4 : (ant.dir + 3) % 4;
            intent.dst_x = ant.x;
            intent.dst_y = ant.y;
            if (intent.new_dir == 0) {
                intent.dst_y -= 1;
            } else if (intent.new_dir == 1) {
                intent.dst_x += 1;
            } else if (intent.new_dir == 2) {
                intent.dst_y += 1;
            } else {
                intent.dst_x -= 1;
            }
            if (wrap) {
                intent.dst_x = wrap_coord(intent.dst_x, n);
                intent.dst_y = wrap_coord(intent.dst_y, n);
            }
            intent.dst_rank = owner_of_row(intent.dst_y, row_start, row_count);
            intents.push_back(intent);
        }

        vector<int> intent_counts;
        vector<int> intent_counts_scatter;
        vector<int> intent_displs;
        vector<int> scatter_displs;
        int local_intent_count = static_cast<int>(intents.size());
        if (rank == 0) {
            intent_counts.resize(world_size);
        }
        MPI_Gather(&local_intent_count, 1, MPI_INT,
                   rank == 0 ? intent_counts.data() : nullptr, 1, MPI_INT,
                   0, MPI_COMM_WORLD);

        vector<int> packed_intents = pack_intents(intents);
        vector<int> gathered_intents;
        vector<int> winner_flags_packed;
        if (rank == 0) {
            intent_counts_scatter = intent_counts;
            intent_displs.resize(world_size);
            scatter_displs.resize(world_size);
            int offset = 0;
            int scatter_offset = 0;
            for (int r = 0; r < world_size; ++r) {
                intent_displs[r] = offset;
                intent_counts[r] *= 7;
                offset += intent_counts[r];

                scatter_displs[r] = scatter_offset;
                scatter_offset += intent_counts_scatter[r];
            }
            gathered_intents.resize(offset);
        }

        MPI_Gatherv(packed_intents.empty() ? nullptr : packed_intents.data(), static_cast<int>(packed_intents.size()), MPI_INT,
                    rank == 0 ? gathered_intents.data() : nullptr,
                    rank == 0 ? intent_counts.data() : nullptr,
                    rank == 0 ? intent_displs.data() : nullptr,
                    MPI_INT, 0, MPI_COMM_WORLD);

        vector<int> local_winner_flags(local_intent_count, 0);
        if (rank == 0) {
            vector<Intent> all_intents = unpack_intents(gathered_intents);
            vector<int> winners(all_intents.size(), 0);
            vector<pair<pair<int, int>, int>> ordered;
            ordered.reserve(all_intents.size());
            for (size_t i = 0; i < all_intents.size(); ++i) {
                ordered.push_back({{all_intents[i].dst_y, all_intents[i].dst_x}, static_cast<int>(i)});
            }
            sort(ordered.begin(), ordered.end(), [&](const auto &lhs, const auto &rhs) {
                const Intent &a = all_intents[lhs.second];
                const Intent &b = all_intents[rhs.second];
                if (a.dst_y != b.dst_y) return a.dst_y < b.dst_y;
                if (a.dst_x != b.dst_x) return a.dst_x < b.dst_x;
                return a.id < b.id;
            });
            int last_x = -1;
            int last_y = -1;
            for (const auto &entry : ordered) {
                int idx = entry.second;
                const Intent &intent = all_intents[idx];
                if (intent.dst_x != last_x || intent.dst_y != last_y) {
                    winners[idx] = 1;
                    last_x = intent.dst_x;
                    last_y = intent.dst_y;
                }
            }
            winner_flags_packed = winners;

            if (gui_mode) {
                int migrations_count = 0;
                for (size_t idx = 0; idx < all_intents.size(); ++idx) {
                    const auto &intent = all_intents[idx];
                    if (winners[idx] == 1) {
                        int cur_color = gui_grid[intent.src_y * n + intent.src_x];
                        int new_color = 1 - cur_color;
                        gui_grid[intent.src_y * n + intent.src_x] = new_color;
                        cout << "FLIP " << intent.src_x << " " << intent.src_y << " " << new_color << endl;

                        gui_ants[intent.id].x = intent.dst_x;
                        gui_ants[intent.id].y = intent.dst_y;
                        gui_ants[intent.id].dir = intent.new_dir;
                        cout << "ANT " << intent.id << " " << intent.dst_x << " " << intent.dst_y << " " << intent.new_dir << endl;

                        int src_rank = owner_of_row(intent.src_y, row_start, row_count);
                        if (intent.dst_rank != src_rank) {
                            migrations_count++;
                        }
                    } else {
                        const auto &ant = gui_ants[intent.id];
                        cout << "ANT " << ant.id << " " << ant.x << " " << ant.y << " " << ant.dir << endl;
                    }
                }
                int black = 0;
                for (uint8_t c : gui_grid) if (c == 1) black++;
                int white = n * n - black;
                cout << "STATS " << black << " " << white << " " << migrations_count << endl;
                cout.flush();
            }
        }

        MPI_Scatterv(rank == 0 ? winner_flags_packed.data() : nullptr,
                     rank == 0 ? intent_counts_scatter.data() : nullptr,
                     rank == 0 ? scatter_displs.data() : nullptr,
                     MPI_INT,
                     local_winner_flags.data(), local_intent_count, MPI_INT,
                     0, MPI_COMM_WORLD);

        vector<Ant> next_ants;
        vector<Ant> send_north;
        vector<Ant> send_south;
        next_ants.reserve(ants.size());
        for (size_t i = 0; i < ants.size(); ++i) {
            if (i >= intents.size() || local_winner_flags[i] == 0) {
                Ant static_ant = ants[i];
                static_ant.steps_matching = 0;
                next_ants.push_back(static_ant);
                continue;
            }

            int local_y = ants[i].y - row_start[rank] + 1;
            int local_x = ants[i].x;
            grid[local_y * n + local_x] = static_cast<uint8_t>(1 - grid[local_y * n + local_x]);

            Ant moved = ants[i];
            moved.dir = intents[i].new_dir;
            moved.x = intents[i].dst_x;
            moved.y = intents[i].dst_y;

            // Highway detection history update
            int step_dx = 0;
            int step_dy = 0;
            if (moved.dir == 0) {
                step_dy = -1;
            } else if (moved.dir == 1) {
                step_dx = 1;
            } else if (moved.dir == 2) {
                step_dy = 1;
            } else {
                step_dx = -1;
            }

            int idx = (step - 1) % 104;
            if (moved.history_dir[idx] == moved.dir && moved.history_dx[idx] == step_dx && moved.history_dy[idx] == step_dy) {
                moved.steps_matching++;
            } else {
                moved.steps_matching = 0;
            }
            moved.history_dir[idx] = moved.dir;
            moved.history_dx[idx] = step_dx;
            moved.history_dy[idx] = step_dy;

            if (moved.steps_matching >= 208) {
                local_highway_detected = true;
            }

            if (intents[i].dst_rank == rank) {
                next_ants.push_back(moved);
            } else {
                int north = (rank - 1 + world_size) % world_size;
                if (intents[i].dst_rank == north) {
                    send_north.push_back(moved);
                } else {
                    send_south.push_back(moved);
                }
            }
        }
        ants.swap(next_ants);

        if (world_size > 1) {
            int north = (rank - 1 + world_size) % world_size;
            int south = (rank + 1) % world_size;

            int send_north_count = static_cast<int>(send_north.size());
            int send_south_count = static_cast<int>(send_south.size());
            int recv_from_north_count = 0;
            int recv_from_south_count = 0;

            MPI_Sendrecv(&send_north_count, 1, MPI_INT, north, 10,
                         &recv_from_south_count, 1, MPI_INT, south, 10,
                         MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            MPI_Sendrecv(&send_south_count, 1, MPI_INT, south, 11,
                         &recv_from_north_count, 1, MPI_INT, north, 11,
                         MPI_COMM_WORLD, MPI_STATUS_IGNORE);

            vector<int> send_north_buf = pack_ants(send_north);
            vector<int> send_south_buf = pack_ants(send_south);
            vector<int> recv_from_north_buf(recv_from_north_count * ANT_PACK_SIZE);
            vector<int> recv_from_south_buf(recv_from_south_count * ANT_PACK_SIZE);

            MPI_Sendrecv(send_north_buf.empty() ? nullptr : send_north_buf.data(), static_cast<int>(send_north_buf.size()), MPI_INT, north, 20,
                         recv_from_south_buf.empty() ? nullptr : recv_from_south_buf.data(), static_cast<int>(recv_from_south_buf.size()), MPI_INT, south, 20,
                         MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            MPI_Sendrecv(send_south_buf.empty() ? nullptr : send_south_buf.data(), static_cast<int>(send_south_buf.size()), MPI_INT, south, 21,
                         recv_from_north_buf.empty() ? nullptr : recv_from_north_buf.data(), static_cast<int>(recv_from_north_buf.size()), MPI_INT, north, 21,
                         MPI_COMM_WORLD, MPI_STATUS_IGNORE);

            vector<Ant> received_north = unpack_ants(recv_from_north_buf);
            vector<Ant> received_south = unpack_ants(recv_from_south_buf);
            ants.insert(ants.end(), received_north.begin(), received_north.end());
            ants.insert(ants.end(), received_south.begin(), received_south.end());
        }

        int local_highway = local_highway_detected ? 1 : 0;
        int global_highway = 0;
        MPI_Allreduce(&local_highway, &global_highway, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
        if (global_highway > 0) {
            if (rank == 0) {
                cout << "Highway detected at step " << step << ". Stopping simulation." << endl;
            }
            steps = step;
            break;
        }

        if (snapshot_k > 0 && step % snapshot_k == 0) {
            char filename[256];
            snprintf(filename, sizeof(filename), "output_step_%06lld.ppm", step);
            gather_and_write_snapshot(filename, grid, ants, n, local_rows, rank, world_size, row_count);
        }
    }

    gather_and_write_snapshot("output_final_mpi.ppm", grid, ants, n, local_rows, rank, world_size, row_count);

    if (rank == 0) {
        if (gui_mode) {
            cout << "FINISHED" << endl;
            cout.flush();
        }
        cout << "MPI simulation complete. Output: output_final_mpi.ppm" << endl;
    }

    MPI_Finalize();
    return 0;
}

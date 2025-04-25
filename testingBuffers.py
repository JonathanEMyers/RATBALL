import collections
buffer_length = 300

buffer_list = collections.deque()

buffer_list.append(collections.deque(maxlen=buffer_length))

buffer_list[0].append(1)
buffer_list[0].append(1)
buffer_list[0].append(1)
buffer_list[0].append(1)
buffer_list[0].append(1)
buffer_list[0].append(1)
buffer_list[0].append(1)
buffer_list[0].append(1)

buffer_list.append(collections.deque(maxlen=buffer_length))
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)
buffer_list[1].append(1)

print(len(buffer_list))
print(len(buffer_list[0]))
print(len(buffer_list[1]))

buffer_list.popleft()

print(len(buffer_list))
print(len(buffer_list[0]))
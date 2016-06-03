
import rospy
import types
import threading


class Node(object):

    def __init__(self, node_name, **kwargs):
        self.node_name = node_name
        self.kwargs = kwargs
        self.m_loop = None
        self.thread = None
        self.cl = None
        self.subscribers = list()
        self.subscribers_init = list()

    def start(self):
        rospy.init_node(self.node_name, **self.kwargs)
        for args, kwargs in self.subscribers:
            self.subscribers_init.append(rospy.Subscriber(*args, **kwargs))
        is_func = isinstance(self.cl, types.FunctionType)
        is_class = isinstance(self.cl, types.TypeType)
        if is_class:
            targ = self.__start_class
        elif is_func:
            targ = self.__start_func
        self.thread = threading.Thread(target=targ,
                                       args=(self.cl,) + self.cl_args,
                                       kwargs=self.cl_kwargs)
        self.thread.daemon = True
        self.thread.start()
        return self

    def subscriber(self, topic_name, msg_type, **kwargs):
        if not "queue_size" in kwargs:
            kwargs["queue_size"] = 1

        def __decorator(func):
            def __inner(msg):
                if "self" in func.func_code.co_varnames:
                    return self.__class_subscriber(func, msg, topic_name)
                else:
                    return self.__function_subscriber(func, msg, topic_name)
            args = [topic_name, msg_type, __inner]
            self.subscribers.append((args, kwargs))
            return func
        return __decorator

    def publisher(self, *upper_args, **kwargs):
        if not "queue_size" in kwargs:
            kwargs["queue_size"] = 1
        if isinstance(upper_args[0], str):
            topic_name, msg_type = upper_args

            def __decorator(func):
                args = [topic_name, msg_type]
                pub = rospy.Publisher(*args, **kwargs)

                def __inner(*args, **kwargs):
                    msg = func(*args, **kwargs)
                    pub.publish(msg)
                    return msg
                return __inner
            return __decorator
        elif isinstance(upper_args[0], types.TypeType):
            return self.__multi_publisher(upper_args[0], **kwargs)

    def start_node(self, *args, **kwargs):
        self.cl_args = args
        self.cl_kwargs = kwargs

        def __inner(cl):
            self.cl = cl
            return cl
        return __inner

    def main_loop(self, *args, **kwargs):
        def __inner(func):
            self.m_loop = func
            self.m_loop_args = list(args)
            self.m_loop_kwargs = kwargs
            return func
        return __inner

    def __multi_publisher(self, msg_type, **kwargs):
        kw = kwargs
        topics = dict()

        def __decorator(func):

            def __inner(*args, **kwargs):
                msg = func(*args, **kwargs)
                return MultiPublisherHelper(msg, msg_type, topics, **kw)

            return __inner
        return __decorator

    def __class_subscriber(self, func, msg, topic_name):
        if func.func_code.co_argcount == 2:
            return func(self.slf, msg)
        elif func.func_code.co_argcount == 3:
            return func(self.slf, msg, topic_name)

    def __function_subscriber(self, func, msg, topic_name):
        if func.func_code.co_argcount == 1:
            return func(msg)
        elif func.func_code.co_argcount == 2:
            return func(msg, topic_name)

    def __start_class(self, cl, *ar, **kw):
        rate = self.__get_rate(self.m_loop_kwargs)
        nd = cl(*ar, **kw)
        self.slf = nd
        if not self.m_loop is None:
            while not rospy.is_shutdown():
                args = [self.slf] + self.m_loop_args
                self.m_loop(*args, **self.m_loop_kwargs)
                rate.sleep()
        return cl

    def __start_func(self, cl, *ar, **kw):
        rate = self.__get_rate(kw)
        while not rospy.is_shutdown():
            cl(*ar, **kw)
            rate.sleep()
        return cl

    def __get_rate(self, kw):
        if "frequency" in kw:
            freq = kw["frequency"]
            del kw["frequency"]
        else:
            freq = "frequency"
        if isinstance(freq, str):
            def_freq = kw.get("default_frequency", 30)
            freq = rospy.get_param(freq, def_freq)
        if "default_frequency" in kw:
            del kw["default_frequency"]
        return rospy.Rate(freq)


class MultiPublisherHelper(object):

    def __init__(self, msg, msg_type, topics, **kwargs):
        self.msg = msg
        self.msg_type = msg_type
        self.topics = topics
        self.kwargs = kwargs

    def publish(self, topic):
        if not topic in self.topics:
            args = [topic, self.msg_type]
            self.topics[topic] = rospy.Publisher(*args, **self.kwargs)
        self.topics[topic].publish(self.msg)
        return self.msg

    def msg(self):
        return self.msg
